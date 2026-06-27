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


def test_005_no_fp_taskiq_broker_task():
    # taskiq uses @broker.task — must NOT fire without a celery import
    src = """
@broker.task
def process_payment(order_id):
    return payment_service.charge(order_id)
"""
    violations = [v for v in analyze_source(src) if v.rule_id == "PYVIBE-005"]
    assert len(violations) == 0


def test_005_no_fp_huey_task():
    # huey uses @huey.task — must NOT fire without a celery import
    src = """
@huey.task
def process_image(path):
    return resize(path)
"""
    violations = [v for v in analyze_source(src) if v.rule_id == "PYVIBE-005"]
    assert len(violations) == 0


def test_005_no_fp_self_huey_task():
    # huey tests use @self.huey.task() — chained Attribute receiver, must NOT fire
    src = """
@self.huey.task()
def my_task(x):
    return x + 1
"""
    violations = [v for v in analyze_source(src) if v.rule_id == "PYVIBE-005"]
    assert len(violations) == 0


def test_005_detects_celery_app_receiver():
    # @celery_app.task — "celery" in receiver name, fire even without import
    src = """
@celery_app.task
def send_notification(user_id):
    push_service.notify(user_id)
"""
    violations = [v for v in analyze_source(src) if v.rule_id == "PYVIBE-005"]
    assert len(violations) == 1
    assert violations[0].function_name == "send_notification"


def test_005_detects_celery_receiver():
    # @celery.task — "celery" in receiver name
    src = """
@celery.task(max_retries=3, queue="webhooks")
def call_webhook(payload):
    requests.post(payload["url"], json=payload)
"""
    violations = [v for v in analyze_source(src) if v.rule_id == "PYVIBE-005"]
    assert len(violations) == 1


def test_005_broker_task_with_celery_import_fires():
    # Non-standard receiver BUT file has explicit celery import → flag it
    src = """
import celery
@broker.task
def process(data):
    return transform(data)
"""
    violations = [v for v in analyze_source(src) if v.rule_id == "PYVIBE-005"]
    assert len(violations) == 1


def test_005_detects_importer_app_receiver():
    # @importer_app.task — "app" substring in receiver name (real-world: GeoNode)
    src = """
@importer_app.task(base=BaseTask, name="myapp.process")
def process_file(file_id):
    storage.process(file_id)
"""
    violations = [v for v in analyze_source(src) if v.rule_id == "PYVIBE-005"]
    assert len(violations) == 1


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


def test_009_downgraded_to_warning_in_test_file():
    src = """
import json
async def async_setup():
    with open("fixture.json") as f:
        return json.load(f)
"""
    violations = analyze_source(src, "tests/conftest.py")
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-009"
    assert violations[0].severity == "WARNING"


def test_009_still_critical_in_production_file():
    src = """
import json
async def read_config():
    with open("config.json") as f:
        return json.load(f)
"""
    violations = analyze_source(src, "app/handlers.py")
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-009"
    assert violations[0].severity == "CRITICAL"


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


# ─── PYVIBE-017: silent except ───────────────────────────────────────────────

def test_017_detects_bare_except_pass():
    src = """
def process():
    try:
        do_work()
    except:
        pass
"""
    violations = analyze_source(src)
    v017 = [v for v in violations if v.rule_id == "PYVIBE-017"]
    assert len(v017) == 1
    assert v017[0].severity == "CRITICAL"


def test_017_detects_bare_except_ellipsis():
    src = """
async def handler():
    try:
        await do_work()
    except:
        ...
"""
    violations = analyze_source(src)
    v017 = [v for v in violations if v.rule_id == "PYVIBE-017"]
    assert len(v017) == 1
    assert v017[0].severity == "CRITICAL"


def test_017_detects_except_exception_pass():
    src = """
async def handler():
    try:
        await process_order()
    except Exception:
        pass
"""
    violations = analyze_source(src)
    v017 = [v for v in violations if v.rule_id == "PYVIBE-017"]
    assert len(v017) == 1
    assert v017[0].severity == "WARNING"


def test_017_detects_except_exception_ellipsis():
    src = """
def sync_worker():
    try:
        process()
    except Exception:
        ...
"""
    violations = analyze_source(src)
    v017 = [v for v in violations if v.rule_id == "PYVIBE-017"]
    assert len(v017) == 1
    assert v017[0].severity == "WARNING"


def test_017_no_false_positive_with_logging():
    src = """
import logging

async def handler():
    try:
        await process_order()
    except Exception as e:
        logging.error(e)
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-017" for v in violations)


def test_017_no_false_positive_specific_exception():
    src = """
async def handler():
    try:
        await process()
    except ValueError:
        pass
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-017" for v in violations)


def test_017_no_false_positive_reraise():
    src = """
async def handler():
    try:
        await process()
    except Exception:
        raise
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-017" for v in violations)


def test_017_no_false_positive_specific_exception_with_pass():
    # KeyError, IOError, etc. — specific types are acceptable patterns
    src = """
def handler():
    try:
        d["key"]
    except KeyError:
        pass
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-017" for v in violations)


def test_017_nosec_b110_suppresses_exception_pass():
    # # nosec B110 on the except line = intentional suppression, must not flag
    src = """
async def shutdown():
    try:
        await conn.close()
    except Exception:  # nosec B110
        pass
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-017" for v in violations)


def test_017_without_nosec_still_flagged():
    # Regression: identical pattern without # nosec B110 must still be detected
    src = """
async def shutdown():
    try:
        await conn.close()
    except Exception:
        pass
"""
    violations = analyze_source(src)
    v017 = [v for v in violations if v.rule_id == "PYVIBE-017"]
    assert len(v017) == 1
    assert v017[0].severity == "WARNING"


def test_017_nosec_without_b110_is_not_suppressed():
    # # nosec alone (no B110 code) does NOT suppress PYVIBE-017.
    # Rationale: generic # nosec targets Bandit rules; PYVIBE-017 is a separate
    # detector and requires the specific B110 code for an explicit opt-out.
    src = """
async def handler():
    try:
        await risky()
    except Exception:  # nosec
        pass
"""
    violations = analyze_source(src)
    v017 = [v for v in violations if v.rule_id == "PYVIBE-017"]
    assert len(v017) == 1


def test_017_nosec_b110_suppresses_bare_except():
    # # nosec B110 also suppresses bare except (same convention)
    src = """
def cleanup():
    try:
        resource.close()
    except:  # nosec B110
        pass
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-017" for v in violations)


# ─── PYVIBE-018: while True without await ────────────────────────────────────

def test_018_detects_while_true_no_await():
    src = """
async def worker():
    while True:
        do_something()
"""
    violations = analyze_source(src)
    v018 = [v for v in violations if v.rule_id == "PYVIBE-018"]
    assert len(v018) == 1
    assert v018[0].severity == "CRITICAL"


def test_018_no_false_positive_with_await_sleep():
    src = """
import asyncio

async def worker():
    while True:
        do_something()
        await asyncio.sleep(1)
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-018" for v in violations)


def test_018_no_false_positive_with_any_await():
    src = """
async def worker():
    while True:
        result = await fetch()
        process(result)
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-018" for v in violations)


def test_018_no_false_positive_in_sync_function():
    # while True in a plain def is fine — rule only applies to async def
    src = """
def worker():
    while True:
        do_something()
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-018" for v in violations)


def test_018_no_false_positive_await_in_nested_if():
    # await inside an if inside the while counts
    src = """
async def worker():
    while True:
        if condition:
            await asyncio.sleep(0)
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-018" for v in violations)


def test_018_detects_await_only_in_nested_function():
    # await is inside a nested async def — doesn't help the outer while True
    src = """
async def worker():
    while True:
        async def inner():
            await asyncio.sleep(1)
        inner()
"""
    violations = analyze_source(src)
    v018 = [v for v in violations if v.rule_id == "PYVIBE-018"]
    assert len(v018) == 1


def test_018_no_false_positive_while_condition():
    # while <non-True condition> is not flagged
    src = """
async def worker():
    while queue:
        item = queue.pop()
        process(item)
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-018" for v in violations)


def test_018_no_false_positive_async_generator_yield():
    # async generator — yield IS a suspension point (caller awaits __anext__)
    src = """
from typing import AsyncIterable

async def stream_items() -> AsyncIterable[str]:
    i = 0
    while True:
        yield f"item {i}"
        i += 1
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-018" for v in violations)


def test_018_no_false_positive_async_generator_yield_from():
    # async generator using yield from — same reasoning
    src = """
async def relay(source):
    while True:
        yield from source
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-018" for v in violations)


def test_018_detects_regular_async_func_while_true_no_await():
    # plain async def (no yield) with while True and no await — must still fire
    src = """
async def worker():
    while True:
        do_something()
"""
    violations = analyze_source(src)
    v018 = [v for v in violations if v.rule_id == "PYVIBE-018"]
    assert len(v018) == 1


def test_018_nested_yield_does_not_affect_outer_func():
    # yield is inside a nested function — outer async def is NOT an async gen
    src = """
async def outer():
    while True:
        def inner():
            yield 1
        do_something()
"""
    violations = analyze_source(src)
    v018 = [v for v in violations if v.rule_id == "PYVIBE-018"]
    assert len(v018) == 1


# ─── PYVIBE-019: retry loop without backoff ──────────────────────────────────

def test_019_detects_for_loop_retry_no_backoff():
    src = """
async def call_api():
    for attempt in range(3):
        try:
            return await client.post(url)
        except Exception:
            continue
"""
    violations = analyze_source(src)
    v019 = [v for v in violations if v.rule_id == "PYVIBE-019"]
    assert len(v019) == 1
    assert v019[0].severity == "WARNING"


def test_019_detects_underscore_range_retry():
    # for _ in range(N) is the canonical anonymous retry counter.
    src = """
async def generate_unique_key(db):
    for _ in range(10):
        key = generate_random_key()
        try:
            await db.insert(key)
            return key
        except UniqueConstraintError:
            continue
    raise RuntimeError("could not generate unique key")
"""
    violations = analyze_source(src)
    v019 = [v for v in violations if v.rule_id == "PYVIBE-019"]
    assert len(v019) == 1


def test_019_no_false_positive_while_out_of_scope():
    # while loops are completely out of scope for PYVIBE-019 v3 — even clear retries.
    src = """
async def retry_while():
    attempt = 0
    while attempt < 3:
        try:
            return await client.post(url)
        except Exception:
            attempt += 1
            continue
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-019" for v in violations)


def test_019_no_false_positive_except_pass_in_for_range():
    # except: pass in for-range does NOT fire — pass is not explicit retry intent.
    # Confirmed by CLEANUP_PASS analysis: 97/186 hits (52.2%) were pass-only FPs.
    src = """
async def warmup():
    for _ in range(10):
        try:
            await client.get(health_url)
        except Exception:
            pass
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-019" for v in violations)


def test_019_no_false_positive_for_i_range_index():
    # for i in range(N) where i is used as an element index is not retry.
    src = """
async def probe_elements(page):
    count = await page.locator(".item").count()
    for i in range(count):
        try:
            text = await page.locator(".item").nth(i).inner_text()
            if text == "target":
                return i
        except Exception:
            continue
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-019" for v in violations)


def test_019_no_false_positive_for_chunk_start_range():
    # for chunk_start in range(0, N, chunk_size): bulk iteration over chunks, not retry.
    src = """
async def bulk_insert(items, chunk_size=100):
    for chunk_start in range(0, len(items), chunk_size):
        chunk = items[chunk_start:chunk_start + chunk_size]
        try:
            await db.bulk_insert(chunk)
        except Exception as e:
            logger.error(e)
            continue
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-019" for v in violations)


def test_019_no_false_positive_bare_sleep_backoff():
    # sleep(N) imported directly (no asyncio./time. prefix) counts as backoff.
    src = """
from time import sleep

async def call_api():
    for _ in range(3):
        try:
            return await client.post(url)
        except Exception:
            sleep(2)
            continue
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-019" for v in violations)


def test_019_no_false_positive_backoff_class_asleep():
    # await backoff.asleep() from a Backoff class counts as backoff.
    src = """
async def retry_with_backoff(backoff):
    for _ in range(5):
        try:
            return await client.post(url)
        except Exception:
            await backoff.asleep()
            continue
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-019" for v in violations)


def test_019_no_false_positive_poll_loop_in_for_range():
    # for _ in range(N) + asyncio.TimeoutError + timeout= kwarg = bounded poll, not retry.
    src = """
import asyncio

async def wait_with_retries(event, max_polls=20):
    for _ in range(max_polls):
        try:
            await asyncio.wait_for(event.wait(), timeout=1.0)
            return True
        except asyncio.TimeoutError:
            continue
    return False
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-019" for v in violations)


def test_019_no_false_positive_escalation_if_raise():
    src = """
async def call_api():
    for attempt in range(3):
        try:
            return await client.post(url)
        except Exception:
            if attempt == 2:
                raise
            continue
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-019" for v in violations)


def test_019_no_false_positive_backoff_asyncio_sleep():
    src = """
import asyncio

async def call_api():
    for attempt in range(3):
        try:
            return await client.post(url)
        except Exception:
            await asyncio.sleep(2 ** attempt)
            continue
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-019" for v in violations)


def test_019_no_false_positive_backoff_library_name():
    src = """
async def call_api():
    for attempt in range(3):
        try:
            return await client.post(url)
        except Exception:
            await exponential_backoff(attempt)
            continue
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-019" for v in violations)


def test_019_no_false_positive_sync_context():
    src = """
def call_api():
    for attempt in range(3):
        try:
            return client.post(url)
        except Exception:
            continue
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-019" for v in violations)


def test_019_no_false_positive_break_no_retry():
    src = """
async def call_api():
    for attempt in range(3):
        try:
            return await client.post(url)
        except Exception:
            break
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-019" for v in violations)


def test_019_no_false_positive_foreach_collection():
    # for item in collection: except: continue is "skip this item", not retry
    src = """
async def process_records(records):
    for record in records:
        try:
            await save(record)
        except Exception:
            continue
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-019" for v in violations)


def test_019_no_false_positive_foreach_variable_iterable():
    # Iterating over a named variable — for-each, not retry
    src = """
async def index_documents(docs):
    for doc in docs:
        try:
            result = await client.index(doc)
        except Exception as e:
            logger.error(e)
            continue
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-019" for v in violations)


def test_019_no_false_positive_foreach_ui_selectors():
    # UI selector probing (dominant FP category from FP audit: UI_SELECTOR)
    src = """
async def find_button(page):
    selectors = ["#btn-submit", ".submit-btn", "button[type=submit]"]
    for selector in selectors:
        try:
            el = await page.wait_for_selector(selector, timeout=2000)
            if el:
                return el
        except Exception:
            continue
    return None
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-019" for v in violations)


def test_019_foreach_outer_range_inner_collection_no_fire():
    # The innermost loop is a for-each, so continue in except is NOT a retry.
    # The outer range() loop is irrelevant to what `continue` resumes.
    src = """
async def batch_retry(items):
    for attempt in range(3):
        for item in items:
            try:
                await process(item)
            except Exception:
                continue
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-019" for v in violations)


def test_019_detects_range_inside_foreach():
    # Inner loop is range() — the continue IS a retry. Should fire.
    src = """
async def fetch_all(urls):
    for url in urls:
        for attempt in range(3):
            try:
                await client.get(url)
                break
            except Exception:
                continue
"""
    violations = analyze_source(src)
    v019 = [v for v in violations if v.rule_id == "PYVIBE-019"]
    assert len(v019) == 1


def test_019_no_false_positive_poll_loop_asyncio_wait_for():
    # while loops are out of scope for PYVIBE-019 v3. No violations expected.
    src = """
import asyncio

async def _run_loop(self):
    while not self._stop.is_set():
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=self.interval_seconds)
            break
        except asyncio.TimeoutError:
            continue
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-019" for v in violations)


def test_019_no_false_positive_poll_loop_queue_get():
    # while loops are out of scope for PYVIBE-019 v3. No violations expected.
    src = """
import asyncio

async def queue_worker(queue):
    while True:
        try:
            item = await asyncio.wait_for(queue.get(), timeout=5.0)
            process(item)
        except asyncio.TimeoutError:
            continue
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-019" for v in violations)


def test_019_no_false_positive_poll_loop_bare_timeout_error():
    # while loops are out of scope for PYVIBE-019 v3. No violations expected.
    src = """
async def wait_for_event(event):
    while True:
        try:
            await some_lib.wait(event, timeout=10)
        except TimeoutError:
            continue
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-019" for v in violations)


def test_019_no_false_positive_poll_loop_pass_body():
    # while + pass: while is out of scope AND pass is not a retry trigger. No violations.
    src = """
import asyncio

async def heartbeat_loop(stop_event):
    while not stop_event.is_set():
        await do_work()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=1)
            break
        except asyncio.TimeoutError:
            pass
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-019" for v in violations)


# ─── PYVIBE-020: put_nowait() without QueueFull handler ──────────────────────

def test_020_detects_put_nowait_in_async_def():
    # async context — most common pattern from the 100-repo scan
    src = """
import asyncio

async def producer(queue, item):
    queue.put_nowait(item)
"""
    violations = analyze_source(src)
    v020 = [v for v in violations if v.rule_id == "PYVIBE-020"]
    assert len(v020) == 1
    assert v020[0].severity == "WARNING"
    assert v020[0].function_name == "producer"


def test_020_detects_put_nowait_in_sync_def():
    # sync context (strawberry/kopf pattern — sync callback feeds an asyncio.Queue)
    src = """
import asyncio

def websocket_receive(self, text_data=None):
    self.message_queue.put_nowait({"message": text_data})
"""
    violations = analyze_source(src)
    v020 = [v for v in violations if v.rule_id == "PYVIBE-020"]
    assert len(v020) == 1
    assert v020[0].function_name == "websocket_receive"


def test_020_detects_put_nowait_at_module_level():
    src = """
import asyncio

q = asyncio.Queue(maxsize=10)
q.put_nowait("startup-event")
"""
    violations = analyze_source(src)
    v020 = [v for v in violations if v.rule_id == "PYVIBE-020"]
    assert len(v020) == 1
    assert v020[0].function_name == "<module>"


def test_020_no_false_positive_asyncio_queuefull():
    src = """
import asyncio

async def producer(queue, item):
    try:
        queue.put_nowait(item)
    except asyncio.QueueFull:
        logger.warning("queue full, dropping item")
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-020" for v in violations)


def test_020_no_false_positive_bare_queuefull_name():
    # from asyncio import QueueFull — bare name, still suppresses
    src = """
from asyncio import QueueFull

async def producer(queue, item):
    try:
        queue.put_nowait(item)
    except QueueFull:
        pass
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-020" for v in violations)


def test_020_no_false_positive_broad_exception():
    # except Exception catches QueueFull — flag suppressed
    src = """
async def producer(queue, item):
    try:
        queue.put_nowait(item)
    except Exception:
        logger.error("failed to enqueue")
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-020" for v in violations)


def test_020_no_false_positive_await_put():
    # await queue.put() is the blocking alternative — different method, no flag
    src = """
import asyncio

async def producer(queue, item):
    await queue.put(item)
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-020" for v in violations)


def test_020_no_false_positive_nested_try_outer_catches():
    # outer try/except asyncio.QueueFull protects inner unguarded put_nowait
    src = """
import asyncio

async def producer(queue, item):
    try:
        try:
            queue.put_nowait(item)
        except ValueError:
            pass
    except asyncio.QueueFull:
        logger.warning("full")
"""
    violations = analyze_source(src)
    assert not any(v.rule_id == "PYVIBE-020" for v in violations)


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
