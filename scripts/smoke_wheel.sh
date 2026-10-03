#!/usr/bin/env bash
# Build the sdist + wheel, install the wheel into a fresh venv and exercise
# the installed CLI from a directory outside the repo — the same thing a user
# gets from `pip install python-vibe-guard`. Catches anything that works from
# a source checkout but is missing from the published artifact (e.g. 0.12.1's
# `pyvibe explain`, which read research/ from outside the package).
#
#   scripts/smoke_wheel.sh [dist-dir]     (dist-dir defaults to a temp dir)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
DIST="${1:-$WORK/dist}"
trap 'rm -rf "$WORK"' EXIT

fail() { echo "SMOKE FAIL: $*" >&2; exit 1; }

python3 -m venv "$WORK/build-venv"
"$WORK/build-venv/bin/pip" install --quiet build
"$WORK/build-venv/bin/python" -m build --outdir "$DIST" "$REPO_ROOT" >"$WORK/build.log" 2>&1 \
  || { cat "$WORK/build.log" >&2; fail "build failed"; }

WHEEL="$(ls "$DIST"/*.whl)"
EXPECTED_VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' "$REPO_ROOT/pyproject.toml")"
echo "wheel: $(basename "$WHEEL") ($(stat -c %s "$WHEEL") bytes)"

python3 -m venv "$WORK/venv"
"$WORK/venv/bin/pip" install --quiet "$WHEEL"
PYVIBE="$WORK/venv/bin/pyvibe"

# Run everything from a scratch dir so nothing can be picked up from the checkout.
mkdir "$WORK/outside" && cd "$WORK/outside"
cp "$REPO_ROOT/demo/bad_async.py" .

got_version="$("$PYVIBE" --version)"
[[ "$got_version" == "pyvibe $EXPECTED_VERSION" ]] || fail "version '$got_version' != $EXPECTED_VERSION"

explain_out="$("$PYVIBE" explain PYVIBE-005)" || fail "explain PYVIBE-005 exited non-zero"
grep -q "Nivel de evidencia" <<<"$explain_out" || fail "explain output has no evidence level"
grep -q "Precisión auditada: 86%" <<<"$explain_out" || fail "explain output has no audited precision"

set +e
"$PYVIBE" bad_async.py --json > scan.json; scan_exit=$?
"$PYVIBE" bad_async.py --sarif --sarif-output results.sarif >/dev/null; sarif_exit=$?
"$PYVIBE" does-not-exist.py >/dev/null 2>&1; missing_exit=$?
set -e
[[ $scan_exit -eq 1 ]] || fail "scan of the demo exited $scan_exit, expected 1"
[[ $sarif_exit -eq 1 ]] || fail "SARIF scan exited $sarif_exit, expected 1"
[[ $missing_exit -eq 2 ]] || fail "missing path exited $missing_exit, expected 2"

"$WORK/venv/bin/python" - <<'EOF'
import json
findings = json.load(open("scan.json"))
rules = {f["rule"] for f in findings}
assert len(rules) == 20, f"expected one finding per rule (20), got {sorted(rules)}"
sarif = json.load(open("results.sarif"))
assert sarif["version"] == "2.1.0"
run = sarif["runs"][0]
assert len(run["results"]) == len(findings), "SARIF and JSON disagree on the finding count"
assert all(r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "bad_async.py"
           for r in run["results"]), "SARIF uri is not relative to the scan"
EOF

echo "SMOKE OK: $(basename "$WHEEL") installed in a clean venv — version, explain, scan, SARIF, exit codes"
