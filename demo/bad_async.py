"""
demo/bad_async.py — one violation per rule (PYVIBE-001 through PYVIBE-013).
Run: python -m pyvibe demo/bad_async.py
Expected: 13 CRITICAL findings.

The sync_function() at the bottom uses the same calls in a sync context
and should produce ZERO findings.
"""
import asyncio
import time
import threading
import requests
import subprocess
import sqlite3
import os
import httpx
from contextvars import ContextVar

request_id = ContextVar('request_id')


# PYVIBE-001 — time.sleep() inside async def → freezes entire event loop
async def process_order(order_id: int):
    time.sleep(2)  # blocks every concurrent task for 2 seconds
    return order_id


# PYVIBE-002 — requests.get() inside async def → synchronous HTTP I/O
async def fetch_user(user_id: int):
    response = requests.get(f"https://api.example.com/users/{user_id}")
    return response.json()


# PYVIBE-003 — asyncio.run() inside async def → RuntimeError at runtime
async def orchestrate():
    result = asyncio.run(process_order(42))  # already inside a running loop
    return result


# PYVIBE-004 — threading.Lock() inside async def → blocks under contention
async def update_counter():
    lock = threading.Lock()  # acquire() blocks the OS thread
    with lock:
        pass


# PYVIBE-005 — @app.task without time_limit → worker hangs forever
@app.task
def process_payment(order_id):
    return external_api.charge(order_id)  # never returns if API is down


# PYVIBE-006 — ContextVar.set() without try/finally → leaks across requests
async def handle_request(req_id: str):
    request_id.set(req_id)  # no reset() in finally → leaks into next task
    await do_work()


# PYVIBE-007 — subprocess.run() inside async def → blocks for subprocess duration
async def transcode_video(path: str):
    subprocess.run(["ffmpeg", "-i", path, "output.mp4"])


# PYVIBE-008 — sqlite3.connect() inside async def → synchronous DB I/O
async def get_users():
    conn = sqlite3.connect("db.sqlite3")  # blocking file open + I/O
    return conn.cursor().execute("SELECT * FROM users").fetchall()


# PYVIBE-009 — open() inside async def → synchronous file I/O
async def read_config():
    with open("config.json") as f:  # blocks until kernel returns file data
        return f.read()


# PYVIBE-010 — httpx.get() inside async def → httpx sync API blocks OS thread
async def fetch_data():
    response = httpx.get("https://api.example.com/data")
    return response.json()


# PYVIBE-011 — os.system() inside async def → blocking OS call, no async equiv
# os.system() here is intentional: this is the anti-pattern PYVIBE-011 detects.
# This file is never executed — it is only parsed as AST by the scanner.
async def run_script():
    os.system("python script.py")  # blocks until child process exits


# PYVIBE-012 — asyncio.create_task() return value discarded → task GC'd silently
async def notify_user(user_id: int):
    asyncio.create_task(send_email(user_id))  # orphaned: Task ref lost immediately


# PYVIBE-013 — asyncio.gather() without return_exceptions=True → first exception leaks tasks
async def fetch_all(urls: list):
    results = await asyncio.gather(*(fetch(u) for u in urls))  # missing return_exceptions=True
    return results


# ── Sync context — should produce ZERO findings ───────────────────────────────
def sync_function():
    time.sleep(1)
    requests.get("https://example.com")
    lock = threading.Lock()
    with lock:
        pass
    subprocess.run(["echo", "hello"])
    sqlite3.connect(":memory:")
    open("demo/bad_async.py").close()
    httpx.get("https://example.com")
    os.system("echo hello")
