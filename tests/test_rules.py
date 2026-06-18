"""
Tests for python-vibe-guard rules.
Each test validates:
  - the anti-pattern IS detected (true positive)
  - the equivalent sync code is NOT detected (no false positive)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyvibe.analyzer import analyze_source


# ─── PYVIBE-001 ──────────────────────────────────────────────────────────────

def test_001_detects_time_sleep_in_async():
    src = """
import time
async def handler():
    time.sleep(5)
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-001"
    assert violations[0].function_name == "handler"


def test_001_no_false_positive_bare_sleep_import():
    src = """
from time import sleep
async def handler():
    sleep(5)
"""
    # bare sleep() no longer flagged — too generic, causes FPs with custom async wrappers
    violations = analyze_source(src)
    assert len(violations) == 0


def test_001_no_false_positive_in_sync():
    src = """
import time
def sync_handler():
    time.sleep(5)
"""
    violations = analyze_source(src)
    assert len(violations) == 0


# ─── PYVIBE-002 ──────────────────────────────────────────────────────────────

def test_002_detects_requests_get_in_async():
    src = """
import requests
async def fetch():
    return requests.get("https://example.com")
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-002"


def test_002_detects_requests_post_in_async():
    src = """
import requests
async def submit():
    return requests.post("https://api.example.com/data", json={})
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-002"


def test_002_no_false_positive_in_sync():
    src = """
import requests
def sync_fetch():
    return requests.get("https://example.com")
"""
    violations = analyze_source(src)
    assert len(violations) == 0


# ─── PYVIBE-003 ──────────────────────────────────────────────────────────────

def test_003_detects_asyncio_run_in_async():
    src = """
import asyncio
async def bad():
    asyncio.run(some_coroutine())
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-003"


def test_003_no_false_positive_in_sync():
    src = """
import asyncio
def main():
    asyncio.run(some_coroutine())
"""
    violations = analyze_source(src)
    assert len(violations) == 0


# ─── PYVIBE-004 ──────────────────────────────────────────────────────────────

def test_004_detects_threading_lock_in_async():
    src = """
import threading
async def handler():
    lock = threading.Lock()
    with lock:
        pass
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-004"


def test_004_detects_threading_rlock_in_async():
    src = """
import threading
async def handler():
    lock = threading.RLock()
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-004"


def test_004_no_false_positive_in_sync():
    src = """
import threading
def sync_handler():
    lock = threading.Lock()
    with lock:
        pass
"""
    violations = analyze_source(src)
    assert len(violations) == 0


# ─── MULTIPLE VIOLATIONS ─────────────────────────────────────────────────────

def test_multiple_violations_in_one_file():
    src = """
import time, requests, asyncio, threading

async def bad_handler():
    time.sleep(1)
    requests.get("https://example.com")
    asyncio.run(some())
    lock = threading.Lock()
"""
    violations = analyze_source(src)
    rule_ids = [v.rule_id for v in violations]
    assert "PYVIBE-001" in rule_ids
    assert "PYVIBE-002" in rule_ids
    assert "PYVIBE-003" in rule_ids
    assert "PYVIBE-004" in rule_ids


def test_no_violations_in_clean_async():
    src = """
import asyncio
import httpx

async def clean_handler():
    await asyncio.sleep(1)
    async with httpx.AsyncClient() as client:
        response = await client.get("https://example.com")
    lock = asyncio.Lock()
    async with lock:
        pass
"""
    violations = analyze_source(src)
    assert len(violations) == 0


# ─── PYVIBE-005 ──────────────────────────────────────────────────────────────

def test_005_detects_app_task_without_time_limit():
    src = """
@app.task
def process_payment(order_id):
    return external_api.charge(order_id)
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-005"
    assert violations[0].function_name == "process_payment"


def test_005_detects_shared_task_without_time_limit():
    src = """
@shared_task
def send_email(user_id):
    email_service.send(user_id)
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-005"
    assert violations[0].function_name == "send_email"


def test_005_no_false_positive_with_soft_time_limit():
    src = """
@app.task(soft_time_limit=30)
def process_payment(order_id):
    return external_api.charge(order_id)
"""
    violations = analyze_source(src)
    assert len(violations) == 0


def test_005_no_false_positive_with_time_limit():
    src = """
@app.task(time_limit=120)
def send_email(user_id):
    email_service.send(user_id)
"""
    violations = analyze_source(src)
    assert len(violations) == 0


def test_005_detects_empty_parens_no_limit():
    src = """
@shared_task()
def generate_report(report_id):
    return heavy_computation(report_id)
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-005"


def test_005_no_false_positive_with_both_limits():
    src = """
@app.task(soft_time_limit=30, time_limit=60)
def process_payment(order_id):
    return external_api.charge(order_id)
"""
    violations = analyze_source(src)
    assert len(violations) == 0


# ─── PYVIBE-007 ──────────────────────────────────────────────────────────────

def test_007_detects_subprocess_run_in_async():
    src = """
import subprocess
async def process_file(path):
    subprocess.run(["ffmpeg", "-i", path, "output.mp4"])
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-007"
    assert violations[0].function_name == "process_file"


def test_007_detects_subprocess_popen_in_async():
    src = """
import subprocess
async def get_output():
    proc = subprocess.Popen(["git", "log"], stdout=-1)
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-007"


def test_007_no_false_positive_bare_import():
    src = """
from subprocess import check_output
async def get_output():
    result = check_output(["git", "log"])
"""
    # bare check_output() no longer flagged — 'call' caused FPs in FastAPI
    violations = analyze_source(src)
    assert len(violations) == 0


def test_007_no_false_positive_in_sync():
    src = """
import subprocess
def sync_process(path):
    subprocess.run(["ffmpeg", "-i", path])
"""
    violations = analyze_source(src)
    assert len(violations) == 0


def test_007_no_false_positive_asyncio_subprocess():
    src = """
import asyncio
async def async_process(path):
    proc = await asyncio.create_subprocess_exec("ffmpeg", "-i", path)
    await proc.communicate()
"""
    violations = analyze_source(src)
    assert len(violations) == 0


# ─── PYVIBE-008 ──────────────────────────────────────────────────────────────

def test_008_detects_sqlite3_connect_in_async():
    src = """
import sqlite3
async def get_users():
    conn = sqlite3.connect("db.sqlite3")
    return conn.cursor().fetchall()
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-008"
    assert violations[0].function_name == "get_users"


def test_008_no_false_positive_in_sync():
    src = """
import sqlite3
def sync_get_users():
    conn = sqlite3.connect("db.sqlite3")
    return conn.cursor().fetchall()
"""
    violations = analyze_source(src)
    assert len(violations) == 0


def test_008_no_false_positive_aiosqlite():
    src = """
import aiosqlite
async def async_get_users():
    async with aiosqlite.connect("db.sqlite3") as db:
        return await db.execute("SELECT * FROM users")
"""
    violations = analyze_source(src)
    assert len(violations) == 0


# ─── PYVIBE-009 ──────────────────────────────────────────────────────────────

def test_009_detects_open_in_async():
    src = """
import json
async def read_config():
    with open("config.json") as f:
        return json.load(f)
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-009"
    assert violations[0].function_name == "read_config"


def test_009_no_false_positive_in_sync():
    src = """
import json
def sync_read():
    with open("config.json") as f:
        return json.load(f)
"""
    violations = analyze_source(src)
    assert len(violations) == 0


def test_009_no_false_positive_aiofiles():
    src = """
import aiofiles
async def async_read():
    async with aiofiles.open("config.json") as f:
        return await f.read()
"""
    violations = analyze_source(src)
    assert len(violations) == 0


# ─── PYVIBE-011 ──────────────────────────────────────────────────────────────

def test_011_detects_os_system_in_async():
    src = """
import os
async def run_script():
    os.system("python script.py")
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-011"
    assert violations[0].function_name == "run_script"


def test_011_detects_os_popen_in_async():
    src = """
import os
async def get_output():
    result = os.popen("ls -la").read()
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-011"


def test_011_no_false_positive_in_sync():
    src = """
import os
def sync_run():
    os.system("python script.py")
"""
    violations = analyze_source(src)
    assert len(violations) == 0


# ─── PYVIBE-010 ──────────────────────────────────────────────────────────────

def test_010_detects_httpx_get_in_async():
    src = """
import httpx
async def fetch_data():
    response = httpx.get("https://api.example.com/data")
    return response.json()
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-010"
    assert violations[0].function_name == "fetch_data"


def test_010_detects_httpx_post_in_async():
    src = """
import httpx
async def submit():
    return httpx.post("https://api.example.com", json={"key": "value"})
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-010"


def test_010_no_false_positive_in_sync():
    src = """
import httpx
def sync_fetch():
    return httpx.get("https://api.example.com")
"""
    violations = analyze_source(src)
    assert len(violations) == 0


def test_010_no_false_positive_async_client():
    src = """
import httpx
async def async_fetch():
    async with httpx.AsyncClient() as client:
        return await client.get("https://api.example.com")
"""
    violations = analyze_source(src)
    assert len(violations) == 0


# ─── PYVIBE-006 ──────────────────────────────────────────────────────────────

def test_006_detects_contextvar_set_without_cleanup():
    src = """
from contextvars import ContextVar
request_id = ContextVar('request_id')

async def handle_request():
    request_id.set('abc-123')
    await process()
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-006"
    assert violations[0].function_name == "handle_request"


def test_006_no_false_positive_in_sync():
    src = """
from contextvars import ContextVar
request_id = ContextVar('request_id')

def sync_handler():
    request_id.set('abc-123')
"""
    violations = analyze_source(src)
    assert len(violations) == 0


def test_006_no_false_positive_yield_dependency():
    src = """
from contextvars import ContextVar
request_id = ContextVar('request_id')

async def setup_request(req_id: str):
    token = request_id.set(req_id)
    yield
    request_id.reset(token)
"""
    # async generators use yield semantics for cleanup — not flagged
    violations = analyze_source(src)
    assert len(violations) == 0


def test_006_no_flag_with_try_finally_reset():
    src = """
from contextvars import ContextVar
request_id = ContextVar('request_id')

async def handle_request():
    token = request_id.set('abc-123')
    try:
        await process()
    finally:
        request_id.reset(token)
"""
    violations = analyze_source(src)
    assert len(violations) == 0


# ─── PYVIBE-012 ──────────────────────────────────────────────────────────────

def test_012_detects_orphan_create_task():
    src = """
import asyncio

async def handler():
    asyncio.create_task(send_email(user))
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-012"
    assert violations[0].function_name == "handler"


def test_012_no_false_positive_with_assignment():
    src = """
import asyncio

async def handler():
    task = asyncio.create_task(send_email(user))
    await task
"""
    violations = analyze_source(src)
    assert len(violations) == 0


def test_012_no_false_positive_in_list_comprehension():
    src = """
import asyncio

async def handler():
    tasks = [asyncio.create_task(f()) for f in fns]
    await asyncio.gather(*tasks, return_exceptions=True)
"""
    violations = analyze_source(src)
    assert len(violations) == 0


def test_012_no_false_positive_in_return():
    src = """
import asyncio

async def make_task():
    return asyncio.create_task(background_work())
"""
    violations = analyze_source(src)
    assert len(violations) == 0


def test_012_no_false_positive_when_awaited():
    src = """
import asyncio

async def handler():
    await asyncio.create_task(send_email(user))
"""
    violations = analyze_source(src)
    assert len(violations) == 0


def test_012_no_false_positive_in_sync():
    src = """
import asyncio

def sync_caller():
    asyncio.create_task(background())
"""
    violations = analyze_source(src)
    assert len(violations) == 0


def test_012_no_false_positive_tg_create_task():
    src = """
import asyncio

async def handler():
    async with asyncio.TaskGroup() as tg:
        tg.create_task(send_email(user))
"""
    violations = analyze_source(src)
    assert len(violations) == 0


# ─── PYVIBE-013 ──────────────────────────────────────────────────────────────

def test_013_detects_gather_without_return_exceptions():
    src = """
import asyncio

async def handler():
    await asyncio.gather(task1(), task2(), task3())
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-013"
    assert violations[0].function_name == "handler"


def test_013_no_false_positive_with_return_exceptions_true():
    src = """
import asyncio

async def handler():
    results = await asyncio.gather(task1(), task2(), return_exceptions=True)
    return results
"""
    violations = analyze_source(src)
    assert len(violations) == 0


def test_013_no_false_positive_in_sync():
    src = """
import asyncio

def sync_caller():
    asyncio.gather(task1(), task2())
"""
    violations = analyze_source(src)
    assert len(violations) == 0


def test_013_flags_return_exceptions_false():
    # Explicit False has the same broken behavior as the default — first
    # exception propagates, remaining tasks leak. Flag it.
    src = """
import asyncio

async def handler():
    await asyncio.gather(task1(), task2(), return_exceptions=False)
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-013"


def test_013_no_false_positive_taskgroup():
    src = """
import asyncio

async def handler():
    async with asyncio.TaskGroup() as tg:
        tg.create_task(task1())
        tg.create_task(task2())
"""
    violations = analyze_source(src)
    assert len(violations) == 0


def test_013_detects_gather_without_await():
    # gather() without return_exceptions is flagged even when not awaited
    src = """
import asyncio

async def handler():
    coro = asyncio.gather(task1(), task2())
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-013"


# ─── PYVIBE-014 ──────────────────────────────────────────────────────────────

def test_014_detects_ensure_future_orphan():
    src = """
import asyncio

async def handler():
    asyncio.ensure_future(coro())
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-014"
    assert violations[0].function_name == "handler"


def test_014_no_false_positive_with_assignment():
    src = """
import asyncio

async def handler():
    task = asyncio.ensure_future(coro())
    await task
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-014" for v in violations)


def test_014_no_false_positive_in_sync():
    src = """
import asyncio

def sync_caller():
    asyncio.ensure_future(coro())
"""
    violations = analyze_source(src)
    assert len(violations) == 0


def test_014_no_false_positive_in_list():
    src = """
import asyncio

async def handler():
    tasks = [asyncio.ensure_future(c()) for c in coros]
    await asyncio.gather(*tasks, return_exceptions=True)
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-014" for v in violations)


# ─── PYVIBE-015 ──────────────────────────────────────────────────────────────

def test_015_detects_loop_run_until_complete():
    src = """
import asyncio

async def handler():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(coro())
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-015"
    assert violations[0].function_name == "handler"


def test_015_no_false_positive_in_sync():
    src = """
import asyncio

def sync_main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(coro())
"""
    violations = analyze_source(src)
    assert len(violations) == 0


def test_015_detects_any_variable_name():
    src = """
import asyncio

async def handler():
    event_loop = asyncio.new_event_loop()
    event_loop.run_until_complete(coro())
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-015"


def test_015_detects_result_used():
    # run_until_complete assigned to a variable is still wrong inside async def
    src = """
import asyncio

async def handler():
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro())
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-015"


# ─── PYVIBE-016 ──────────────────────────────────────────────────────────────

def test_016_detects_httpx_client_in_async():
    src = """
import httpx

async def handler():
    client = httpx.Client()
    response = client.get("https://example.com")
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-016"
    assert violations[0].function_name == "handler"


def test_016_no_false_positive_async_client():
    src = """
import httpx

async def handler():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://example.com")
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-016" for v in violations)


def test_016_no_false_positive_in_sync():
    src = """
import httpx

def sync_handler():
    client = httpx.Client()
    response = client.get("https://example.com")
"""
    violations = analyze_source(src)
    assert len(violations) == 0


def test_016_detects_inline_instantiation():
    # Client created inline without assignment is still flagged
    src = """
import httpx

async def handler():
    response = httpx.Client().get("https://example.com")
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-016"


# ─── Fix 1: test-file downgrade extended to PYVIBE-001 and PYVIBE-007 ────────

def test_001_downgraded_to_warning_in_test_file():
    src = """
import time

async def setup():
    time.sleep(0.1)
"""
    violations = analyze_source(src, "test_something.py")
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-001"
    assert violations[0].severity == "WARNING"


def test_001_still_critical_in_production_file():
    src = """
import time

async def handler():
    time.sleep(1)
"""
    violations = analyze_source(src, "app/handlers.py")
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-001"
    assert violations[0].severity == "CRITICAL"


def test_007_downgraded_to_warning_in_tests_dir():
    src = """
import subprocess

async def start_service():
    subprocess.run(["uvicorn", "app:app"])
"""
    violations = analyze_source(src, "tests/conftest.py")
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-007"
    assert violations[0].severity == "WARNING"


def test_007_still_critical_in_production_file():
    src = """
import subprocess

async def handler():
    subprocess.run(["convert", "input.jpg", "output.png"])
"""
    violations = analyze_source(src, "app/worker.py")
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-007"
    assert violations[0].severity == "CRITICAL"


# ─── Fix 2: downgrade_in_tests and skip_test_files API ───────────────────────

def test_downgrade_all_rules_in_test_file():
    from pyvibe.analyzer import ALL_RULE_IDS
    src = """
import time

async def setup():
    time.sleep(0.1)
"""
    violations = analyze_source(src, "test_something.py", downgrade_in_tests=ALL_RULE_IDS)
    assert len(violations) == 1
    assert violations[0].severity == "WARNING"


def test_no_downgrade_when_empty_set():
    src = """
import time

async def setup():
    time.sleep(0.1)
"""
    violations = analyze_source(src, "test_something.py", downgrade_in_tests=frozenset())
    assert len(violations) == 1
    assert violations[0].severity == "CRITICAL"


def test_skip_test_files_excludes_test_file(tmp_path):
    from pyvibe.analyzer import analyze_directory
    test_file = tmp_path / "test_something.py"
    test_file.write_text(
        "import time\nasync def setup():\n    time.sleep(0.1)\n"
    )
    results = analyze_directory(tmp_path, skip_test_files=True)
    assert len(results) == 0


def test_skip_test_files_keeps_production_file(tmp_path):
    from pyvibe.analyzer import analyze_directory
    prod_file = tmp_path / "handler.py"
    prod_file.write_text(
        "import time\nasync def handler():\n    time.sleep(1)\n"
    )
    results = analyze_directory(tmp_path, skip_test_files=True)
    assert len(results) == 1


def test_skip_test_files_false_keeps_test_file(tmp_path):
    from pyvibe.analyzer import analyze_directory
    test_file = tmp_path / "test_something.py"
    test_file.write_text(
        "import time\nasync def setup():\n    time.sleep(0.1)\n"
    )
    results = analyze_directory(tmp_path, skip_test_files=False)
    assert len(results) == 1


# ─── Fix 3: threading.Event excluded from PYVIBE-004 ─────────────────────────

def test_004_no_false_positive_threading_event():
    src = """
import threading

async def handler():
    event = threading.Event()
    event.set()
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-004" for v in violations)


def test_004_no_false_positive_event_bare_import():
    src = """
from threading import Event

async def handler():
    ev = Event()
    ev.wait(timeout=1.0)
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-004" for v in violations)


def test_004_still_detects_lock_after_event_exclusion():
    src = """
import threading

async def handler():
    lock = threading.Lock()
    with lock:
        pass
"""
    violations = analyze_source(src)
    assert any(v.rule_id == "PYVIBE-004" for v in violations)


def test_004_still_detects_condition_after_event_exclusion():
    src = """
import threading

async def handler():
    cond = threading.Condition()
"""
    violations = analyze_source(src)
    assert any(v.rule_id == "PYVIBE-004" for v in violations)


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL {test.__name__}: {e}")
            failed += 1
    print(f"\n  {passed} passed, {failed} failed")
