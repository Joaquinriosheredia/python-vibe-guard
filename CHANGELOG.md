# Changelog

All notable changes to python-vibe-guard are recorded here.

## Unreleased

### Changed
- **Path-based severity (all rules)**: a CRITICAL finding whose file path has a
  non-production directory segment — `tests/`, `test/`, `scripts/`, `wip/`, `spike/`,
  `examples/` (full-segment match) — or a test filename (`test_*.py`, `*_test.py`,
  `conftest.py`) is downgraded to WARNING, never silenced. Full-segment match only, so
  `com/example/` (segment `example`) and `app/my_tests_utils.py` are not downgraded.
  The CLI applies the same rule as the library (previously it passed the short
  per-rule list), so `--downgrade-in-tests` is now the default and kept only for compatibility.
  Only directory segments **inside the scanned root** count: a repository cloned under
  `.../scripts/x` or `.../tests/x` is no longer downgraded as a whole, with an absolute or a
  relative path (also for `--no-test-files`). The root is the scanned directory, the git
  repository for `pyvibe review`, and the file's own directory for a single-file scan, where
  only the filename counts.
- **PYVIBE-017** (silent except): by default now reports only a bare `except:` and an
  `except BaseException` with an empty body (pass/...), and only **in an async function**
  (they swallow CancelledError/KeyboardInterrupt/SystemExit). A plain `except Exception: pass`
  is now **opt-in** (`report_broad_except = true` under `[tool.pyvibe]`, or
  `--report-broad-except`); a bare except in synchronous code is no longer reported.
  Within an async function, the CRITICAL is raised only when the `try` body contains a
  suspension point (`await`, `async for`, `async with`) where a cancellation can be delivered;
  a try with only synchronous work (e.g. `future.result()`) is not reported (dev-labels
  DL-055..DL-057).
- **PYVIBE-013** (`asyncio.gather` without `return_exceptions=True`): added a containment
  analysis so a gather is not reported when every gathered awaitable resolves to a function
  that contains its exceptions (the awaited I/O is guarded by a `try`/`except` that returns,
  following nested defs, `self`/`cls` methods and module functions, with recursion assumed
  contained). Reduces false positives on guarded fan-out patterns.

### Known limitations
- **PYVIBE-013**: a *synchronous* statement that raises **before** the `try` (e.g. a
  validation such as `scope_guard.assert_in_scope(...)`) is a **false negative** — it is not
  detected. The rule intentionally allows ordinary synchronous statements outside the try so
  the common guarded pattern is not over-reported. Tracked by an `xfail` regression test
  (`test_013_B2_sync_validation_before_try_known_false_negative`) and in the rule's
  `pyvibe explain` text.
- **PYVIBE-007**: a `subprocess.Popen` whose pipe is read synchronously (e.g.
  `p.stdout.read()` in an `async def`) without `.wait()`/`.communicate()` blocks the event
  loop but is a **false negative**: only `.wait()`/`.communicate()` count as waiting. Found
  with a synthetic example (no corpus verdict). Tracked by an `xfail` regression test
  (`test_007_popen_blocking_stdout_read_known_false_negative`) and in the rule's
  `pyvibe explain` text.
