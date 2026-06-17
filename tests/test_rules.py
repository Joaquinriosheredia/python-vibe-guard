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


def test_001_detects_bare_sleep_import_in_async():
    src = """
from time import sleep
async def handler():
    sleep(5)
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-001"


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


def test_007_detects_bare_import_in_async():
    src = """
from subprocess import check_output
async def get_output():
    result = check_output(["git", "log"])
"""
    violations = analyze_source(src)
    assert len(violations) == 1
    assert violations[0].rule_id == "PYVIBE-007"


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
