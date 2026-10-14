# Changelog

All notable changes to python-vibe-guard are recorded here.

## Unreleased

### Changed
- **Path-based severity (all rules)**: a CRITICAL finding whose file path has a
  non-production directory segment — `tests/`, `test/`, `scripts/`, `wip/`, `spike/`,
  `examples/` (full-segment match) — or a test filename (`test_*.py`, `*_test.py`,
  `conftest.py`) is downgraded to WARNING, never silenced. Full-segment match only, so
  `com/example/` (segment `example`) and `app/my_tests_utils.py` are not downgraded.
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
