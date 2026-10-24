# Changelog

All notable changes to python-vibe-guard are recorded here.

## Unreleased

False positives of test-corpus-2 (vibe-guard-evaluation `test-corpus-2/FP-ANALYSIS.md`), each
with a regression test from the reviewed code (`tests/test_tc2_regressions.py`). Declared in
`test-corpus-3/PREREGISTRATION.md` before these changes.

### ⚠ BREAKING — default severities (CI gates may report fewer CRITICAL)
- **PYVIBE-005** (Celery without time limit) is now **WARNING**. test-corpus-2: 0 TP of 13.
  A receiver imported from a module counts as Celery's only if the module's path contains
  `celery` or the file imports `celery`. A file importing Procrastinate, Huey, Dramatiq,
  taskiq, arq, RQ, SAQ or Faust (and not `celery`) is not reported (13 FPs were
  Procrastinate's `@task_app.task`).
- **PYVIBE-013** (`gather()` without `return_exceptions`) is now **WARNING**. test-corpus-2:
  2 TP of 10; the containment was in other modules.
- **Blocking rules at start-up:** a CRITICAL of PYVIBE-001/002/004/007/008/009/010/011/016/018
  directly in the module-level `async def` that the module passes to `asyncio.run()` (outside
  any `async def`) is **WARNING**, with the reason in the message (P079, P080, P083, P084,
  P099, P001).

### Changed
- **PYVIBE-011:** `os.waitpid(…, WNOHANG)` is not reported (P119, P122).
- **PYVIBE-018:** a bounded "first free name" search is not reported (P014, P078).
- **PYVIBE-017:** an empty handler inside a handler of the same function that ends with a bare
  `raise` is not reported (P043).
- **Messages reworded** to state the mechanism and its condition instead of the worst case:
  PYVIBE-005, 009, 011, 012, 013, 018. A baseline entry keyed on an old message no longer
  matches.
- The demo gives 20 findings: 16 CRITICAL and 4 WARNING.

## 0.14.0 — 2026-10-14

vibe-guard Phase 1 precision work (#9, #10, #11, #12, #13).

### ⚠ BREAKING — default behaviour changes (CI gates may report fewer CRITICAL/WARNING)
- **Path-based severity, all rules** (#11, #13): a CRITICAL finding is downgraded to
  WARNING, never silenced, when it is in a test filename (`test_*.py`, `*_test.py`,
  `conftest.py`) or under a non-production directory segment (`tests/`, `test/`,
  `scripts/`, `wip/`, `spike/` or `examples/`).
  - The match is on full segments only: `com/example/` (segment `example`) and
    `app/my_tests_utils.py` are not downgraded.
  - Before 0.14.0 only a per-rule subset was downgraded, and only under `tests/`/`test/`.
  - The CLI now applies the same rule as the library, so `--downgrade-in-tests` is the
    default and is kept only for compatibility.
  - Only the **scanned root's own name and the segments inside it** count; for a single
    file, its immediate directory as passed. **The directories above never count.** A
    repository cloned under `.../scripts/my-repo` and scanned by absolute path or as `.` is
    not downgraded as a whole (this also applies to `--no-test-files`), while
    `pyvibe scripts/` and `pyvibe tests/foo.py` are. The root is the scanned directory, or
    the git repository for `pyvibe review`.
- **PYVIBE-017** (silent except) (#12):
  - **Default:** reports only a bare `except:` and an `except BaseException` with an empty
    body (`pass`/`...`), and only **in an async function** whose `try` body contains a
    suspension point (`await`, `async for` or `async with`) where a cancellation can be
    delivered. Both swallow `CancelledError`, `KeyboardInterrupt` and `SystemExit`.
  - **No longer reported by default:** a bare except in synchronous code, and a `try` that
    holds only synchronous work (e.g. `future.result()`).
  - **`except Exception: pass` is now opt-in** (WARNING): set `report_broad_except = true`
    under `[tool.pyvibe]` or pass `--report-broad-except`. It used to be reported by
    default.
  - The demo's PYVIBE-017 example is now an async `except BaseException: pass`, so the demo
    gives 20 findings: 18 CRITICAL and 2 WARNING.

### Changed
- **PYVIBE-007** (#9): `subprocess.Popen` is reported only when its handle is waited on
  synchronously (`.wait()` / `.communicate()`) in the same function. A `Popen` that only
  starts a child and returns does not block, so it is not reported.
  `subprocess.run`/`call`/`check_output` are unchanged.
- **PYVIBE-013** (`asyncio.gather` without `return_exceptions=True`) (#10): the containment
  analysis is relaxed from the 0.13.0 rule. A gather is not reported when every gathered
  awaitable resolves to a function that contains its exceptions: the awaited I/O is guarded
  by a `try`/`except` that returns. The analysis follows nested defs, `self`/`cls` methods
  and module functions, and assumes recursion is contained. This reduces false positives on
  guarded fan-out patterns.

### Known limitations (known false negatives)
- **PYVIBE-013**: a *synchronous* statement that raises **before** the `try` (e.g. a
  validation such as `scope_guard.assert_in_scope(...)`) is a **false negative**: it is not
  detected.
  - The rule intentionally allows ordinary synchronous statements outside the try, so that
    the common guarded pattern is not over-reported.
  - Tracked by an `xfail` regression test
    (`test_013_B2_sync_validation_before_try_known_false_negative`) and in the rule's
    `pyvibe explain` text.
- **PYVIBE-007**: a `subprocess.Popen` whose pipe is read synchronously (e.g.
  `p.stdout.read()` in an `async def`) without `.wait()`/`.communicate()` blocks the event
  loop, but it is a **false negative**: only `.wait()`/`.communicate()` count as waiting.
  - Found with a synthetic example (no corpus verdict).
  - Tracked by an `xfail` regression test
    (`test_007_popen_blocking_stdout_read_known_false_negative`) and in the rule's
    `pyvibe explain` text.
- **PYVIBE-017**: with the new default, an empty `except:`/`except BaseException` whose
  `try` has no suspension point is not reported. A `KeyboardInterrupt` arriving there in
  synchronous code can still be swallowed.
