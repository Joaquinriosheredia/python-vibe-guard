# python-vibe-guard — Gap Analysis

**Scan date:** 2026-06-20  
**Sample:** 100 repos, 64,335 .py files, 3,639 violations  
**Purpose:** identify async anti-patterns that appear in 5+ repos but are NOT detected by any current rule

---

## Finding 1 — `asyncio.create_task()` inside signal handler lambda (fire-and-forget)

**Pattern:** `loop.add_signal_handler(sig, lambda: asyncio.create_task(coro()))`

**Not caught by:** PYVIBE-012 only flags `create_task()` whose return value is discarded as a **statement**. Here the call is inside a lambda passed to `add_signal_handler` — the task is created when the signal fires, at which point there is no variable to assign to and the task reference is immediately lost.

**Why it matters:** the task runs to completion (or raises) with no handle to cancel it, no exception surfaced, and no way to know if the signal handler fired correctly.

**Repos confirmed (5+):**
- `plastic-labs/honcho`
- `nolar/kopf`
- `aiogram/aiogram`
- `home-assistant/core`
- `amidaware/tacticalrmm`

**Code example — `plastic-labs/honcho` (`src/deriver/queue_manager.py`):**
```python
loop = asyncio.get_running_loop()
signals = (signal.SIGTERM, signal.SIGINT)
for sig in signals:
    loop.add_signal_handler(
        sig, lambda s=sig: asyncio.create_task(self.shutdown(s))
        #                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        #  Task created when signal fires — reference immediately lost.
        #  If shutdown() raises, the exception is swallowed silently.
    )
```

**Correct pattern:**
```python
def _handle_signal(sig):
    task = asyncio.create_task(self.shutdown(sig))
    task.add_done_callback(lambda t: t.exception())  # surface errors

loop.add_signal_handler(sig, lambda s=sig: _handle_signal(s))
```

**Detection idea (PYVIBE-020):** Visit `ast.Call` nodes where `func` is `loop.add_signal_handler` or `asyncio.get_event_loop().add_signal_handler`; check if any `ast.Lambda` body contains `asyncio.create_task(` or `asyncio.ensure_future(` without capturing the return value.

---

## Finding 2 — `aiohttp.ClientSession()` instantiated outside `async with`

**Pattern:** `self.session = aiohttp.ClientSession()` inside `async def`, never closed with `await session.close()` or `async with`.

**Not caught by:** PYVIBE-016 targets `httpx.Client()` only. There is no rule for `aiohttp.ClientSession()` lifetime management.

**Why it matters:** `ClientSession` holds a connection pool and an internal connector. If not explicitly closed, it leaks open TCP connections for the process lifetime. In long-running services this causes "Unclosed client session" warnings and eventual resource exhaustion. aiohttp itself emits `ResourceWarning` at interpreter shutdown.

**Repos confirmed (7):**
- `bmoscon/cryptofeed` (3 instances)
- `zhinianboke/xianyu-auto-reply` (1 instance)
- `aiortc/aiortc` (examples — 1 instance)
- `faust-streaming/faust` (examples — 1 instance)
- `vastsa/FileCodeBox` (2 instances)
- `Neoteroi/BlackSheep` (client helpers)
- `nolar/kopf` (HTTP push channel)

**Code example — `bmoscon/cryptofeed` (`cryptofeed/connection.py`):**
```python
async def _open(self):
    if self.is_open:
        LOG.warning('%s: HTTP session already created', self.id)
    else:
        LOG.debug('%s: create HTTP session', self.id)
        self.conn = aiohttp.ClientSession()   # ← no async with, no explicit close
        self.sent = 0
        self.received = 0
        self.last_message = None

async def read(self, address, ...):
    if not self.is_open:
        await self._open()
    async with self.conn.get(address, ...) as response:
        ...
    # Session is never closed — connection pool leaks on object disposal
```

**Correct pattern:**
```python
async with aiohttp.ClientSession() as session:
    async with session.get(url) as response:
        data = await response.json()

# or, for long-lived sessions:
self._session = aiohttp.ClientSession()
# ... later, in cleanup:
await self._session.close()
self._session = None
```

**Detection idea (PYVIBE-020 or new rule):** Detect `aiohttp.ClientSession()` call in `async def` that is NOT the direct target of an `async with` statement. Mirror PYVIBE-016 logic but for `aiohttp.ClientSession` instead of `httpx.Client`.

---

## Finding 3 — `asyncio.Queue.put_nowait()` in async def on bounded queue

**Pattern:** `queue.put_nowait(item)` called in an async function where the queue may be bounded (`maxsize > 0`), with no `QueueFull` handler.

**Not caught by:** no current rule covers `Queue.put_nowait()`.

**Why it matters:** `put_nowait()` raises `asyncio.QueueFull` immediately if the queue has reached `maxsize`. Unlike `await queue.put(item)` (which blocks until space is available), `put_nowait` drops the item if not caught. In high-throughput event pipelines this causes silent data loss — no log, no metric, no retry.

**Repos confirmed (25):**
- `nolar/kopf` — Kubernetes event queue
- `strawberry-graphql/strawberry` — WebSocket message queue
- `google-gemini/genai-processors` — streaming pipeline queues
- `xerrors/Yuxi` — knowledge graph processing
- `faust-streaming/faust` — stream processing reports
- …and 20 more

**Code example — `nolar/kopf` (`kopf/_core/engines/posting.py`):**
```python
if running_loop is loop:
    queue.put_nowait(event)          # ← raises QueueFull if queue is bounded
else:
    loop.call_soon_threadsafe(queue.put_nowait, event)
```

**Code example — `strawberry-graphql/strawberry` (`strawberry/channels/handlers/ws_handler.py`):**
```python
def websocket_receive(self, text_data=None, bytes_data=None):
    # Called from sync Django channels layer — must use put_nowait
    self.message_queue.put_nowait({"message": text_data, "disconnected": False})
    # If message_queue is bounded and full, this raises QueueFull silently
```

**Correct pattern:**
```python
try:
    queue.put_nowait(item)
except asyncio.QueueFull:
    logger.warning("Queue full, dropping item: %r", item)
    # or: await queue.put(item) if blocking is acceptable
```

**Detection idea:** Flag `put_nowait(` calls inside `async def` where the receiver is an `asyncio.Queue` (or unknown — conservative) and there is no surrounding `try/except` catching `QueueFull` or `Exception`.

---

## Summary

| Gap | Pattern | Repos (100-sample) | Severity | Status |
|-----|---------|-------------------|----------|--------|
| Signal-handler fire-and-forget | `add_signal_handler(sig, lambda: create_task(...))` | 5+ | WARNING | open — candidate PYVIBE-021 |
| `aiohttp.ClientSession()` not in `async with` | `self.session = aiohttp.ClientSession()` | 7 | WARNING | open — candidate PYVIBE-022 |
| `Queue.put_nowait()` without QueueFull handler | `queue.put_nowait(x)` in async def | 25 | WARNING | **IMPLEMENTED** as PYVIBE-020 (v0.7.0) |

The fire-and-forget signal handler and the aiohttp session leak are close enough in theme (resource lifetime mismanagement) that they could share a single detection pass. The `put_nowait` gap is independent and high-prevalence (25% of repos).

**Note on `list.append(create_task(...))` — NOT a gap:**  
All 9 repos found doing `tasks.append(asyncio.create_task(...))` subsequently call `await asyncio.gather(*tasks)` or `await asyncio.wait(tasks)`. PYVIBE-012 correctly does not flag these (the return value is captured). The pattern is valid and properly awaited in every confirmed instance.
