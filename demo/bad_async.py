"""
demo/bad_async.py — contains all 4 PYVIBE violations intentionally.
Run: python -m pyvibe demo/bad_async.py
Expected: 4 CRITICAL findings.
"""
import asyncio
import time
import threading
import requests


# PYVIBE-001 — time.sleep() inside async def
async def process_order(order_id: int):
    time.sleep(2)  # blocks event loop
    return order_id


# PYVIBE-002 — requests.get() inside async def
async def fetch_user(user_id: int):
    response = requests.get(f"https://api.example.com/users/{user_id}")
    return response.json()


# PYVIBE-003 — asyncio.run() inside async def
async def orchestrate():
    result = asyncio.run(process_order(42))  # RuntimeError at runtime
    return result


# PYVIBE-004 — threading.Lock() instantiated inside async def
async def update_counter():
    lock = threading.Lock()  # blocks event loop under contention
    with lock:
        pass


# These should NOT trigger (sync context)
def sync_function():
    time.sleep(1)
    requests.get("https://example.com")
    lock = threading.Lock()
    with lock:
        pass
