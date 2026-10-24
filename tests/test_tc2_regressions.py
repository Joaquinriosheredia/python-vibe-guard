"""Regression tests for the false positives of test-corpus-2 (vibe-guard-evaluation
`test-corpus-2/FP-ANALYSIS.md`, development data).

Each FP fixture is the code of the reviewed finding at its pinned commit, trimmed to what
the rule reads, with its review-set ID and repository. Each fix also has a positive
control: the pattern the rule exists for is still reported.
"""
import textwrap

from pyvibe.analyzer import analyze_source


def _rule(src, rule_id, path="app/module.py"):
    return [v for v in analyze_source(textwrap.dedent(src), path) if v.rule_id == rule_id]


# ── PYVIBE-005: Procrastinate taken for Celery (P009…P050, geolens-io/geolens) ──────

def test_005_p046_procrastinate_task_app_imported_from_project_module_not_reported():
    # backend/app/processing/ingest/tasks_vrt.py:455-457 (task_app = procrastinate App,
    # defined in tasks_common.py:227; no Celery in the repository)
    assert _rule('''
        from app.processing.ingest.tasks_common import (
            task_app,
        )

        @task_app.task(queue="raster", retry=0)
        async def ingest_vrt(job_id: str) -> None:
            ...
    ''', "PYVIBE-005") == []


def test_005_procrastinate_app_defined_in_file_not_reported():
    # backend/app/processing/ingest/tasks_common.py:23,227
    assert _rule('''
        from procrastinate import App, PsycopgConnector

        task_app = App(connector=PsycopgConnector())

        @task_app.task(queue="ingest")
        async def refresh():
            ...
    ''', "PYVIBE-005") == []


def test_005_celery_app_imported_from_celery_module_still_reported_as_warning():
    v = _rule('''
        from proj.celery import app

        @app.task
        def charge(order_id):
            return payments.charge(order_id)
    ''', "PYVIBE-005")
    assert len(v) == 1 and v[0].severity == "WARNING"
    assert "can hang forever" not in v[0].message
    assert "global task_time_limit" in v[0].message


def test_005_receiver_imported_from_project_module_with_celery_import_still_reported():
    assert len(_rule('''
        from celery import shared_task
        from proj.worker import app

        @app.task
        def charge(order_id):
            return payments.charge(order_id)
    ''', "PYVIBE-005")) == 1


# ── PYVIBE-013: demoted to WARNING (P002…P118: callees contain their exceptions) ────

def test_013_p002_is_warning_and_message_says_this_call():
    # server/app/routers/domains.py:110 (Anil-matcha/open-agent-email): the check_*
    # callees catch DNS errors in another module; not decidable here.
    v = _rule('''
        import asyncio
        from app.services import domain_dns

        async def verify_domain(domain):
            mx, spf, dkim, dmarc = await asyncio.gather(
                asyncio.to_thread(domain_dns.check_mx, domain),
                asyncio.to_thread(domain_dns.check_spf, domain),
                asyncio.to_thread(domain_dns.check_dkim, domain),
                asyncio.to_thread(domain_dns.check_dmarc, domain),
            )
    ''', "PYVIBE-013")
    assert len(v) == 1 and v[0].severity == "WARNING"
    assert "nobody observing" not in v[0].message
    assert v[0].message.endswith("not observed by this call")


# ── Blocking rules in the asyncio.run() entry coroutine (P079, P080, P083, P084, P099, P001) ──

def test_009_p079_config_read_in_asyncio_run_entry_coroutine_is_warning():
    # consortium/client/start_client.py:22-32, 126-132 (not-sekiun/Consortium)
    v = _rule('''
        import asyncio
        import json

        async def _start_client(arguments) -> None:
            client_config_filepath = arguments.client_config
            try:
                with open(client_config_filepath) as file:
                    json_data = json.load(fp=file)
            except FileNotFoundError:
                return
            await Client(client_config=json_data).run()


        def main(arguments) -> None:
            asyncio.run(_start_client(arguments))
    ''', "PYVIBE-009")
    assert len(v) == 1 and v[0].severity == "WARNING"
    assert "asyncio.run()" in v[0].message and "_start_client()" in v[0].message


def test_009_p099_smoke_script_main_under_dunder_main_is_warning():
    # mcps/custom/tts-mcp/live_smoke.py:28-61 (OtoDock/oto-dock)
    v = _rule('''
        import asyncio
        import httpx

        async def main() -> int:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post("/v1/audio/tts/generate", json={})
                out = "/tmp/tts-smoke.wav"
                with open(out, "wb") as f:
                    f.write(resp.content)
            return 0


        if __name__ == "__main__":
            raise SystemExit(asyncio.run(main()))
    ''', "PYVIBE-009")
    assert len(v) == 1 and v[0].severity == "WARNING"


def test_008_p001_demo_main_is_warning():
    # example_usage.py:104-204 (AhmadHassan-BTed/OpenOPC-Shadow-Adapter)
    v = _rule('''
        import asyncio
        import sqlite3

        async def main() -> None:
            await adapter.start()
            db = sqlite3.connect(str(opc_store_path))


        if __name__ == "__main__":
            asyncio.run(main())
    ''', "PYVIBE-008")
    assert len(v) == 1 and v[0].severity == "WARNING"


def test_entry_coroutine_positive_controls_stay_critical():
    # A request handler, a coroutine run by something else, and a nested async def of the
    # entry coroutine are not the entry coroutine itself.
    v = _rule('''
        import asyncio

        async def handler(request):
            with open(request.path) as f:
                return f.read()

        async def main():
            async def inner():
                with open("x") as f:
                    return f.read()
            await inner()

        async def other():
            with open("y") as f:
                return f.read()

        asyncio.run(main())
        loop.run_until_complete(other())
    ''', "PYVIBE-009")
    assert [x.severity for x in v] == ["CRITICAL", "CRITICAL", "CRITICAL"]
    assert "asyncio.run()" not in v[0].message


def test_entry_coroutine_needs_asyncio_run_outside_any_async_def():
    # asyncio.run() inside an async def is the PYVIBE-003 error, not a program entry point
    # (demo/bad_async.py).
    v = _rule('''
        import asyncio

        async def process_order(order_id):
            with open("orders.json") as f:
                return f.read()

        async def nested_run():
            result = asyncio.run(process_order(42))
    ''', "PYVIBE-009")
    assert [x.severity for x in v] == ["CRITICAL"]


def test_009_new_message_states_the_mechanism_not_the_worst_case():
    v = _rule('''
        async def handler(path):
            with open(path) as f:
                return f.read()
    ''', "PYVIBE-009")
    assert v[0].message.startswith("open() inside async def runs on the event loop")


# ── PYVIBE-011: os.waitpid(…, os.WNOHANG) does not block (P119, P122) ───────────────

def test_011_p119_waitpid_wnohang_polled_with_sleep_not_reported():
    # proxy/services/mcp/mcp_installer.py:110-125 (OtoDock/oto-dock)
    assert _rule('''
        import asyncio
        import os

        async def _reap_group(pgid: int) -> None:
            loop = asyncio.get_running_loop()
            deadline = loop.time() + 1.0
            while True:
                try:
                    pid, _ = os.waitpid(-pgid, os.WNOHANG)
                except ChildProcessError:
                    return
                if pid == 0:
                    if loop.time() >= deadline:
                        return
                    await asyncio.sleep(0.05)
    ''', "PYVIBE-011") == []


def test_011_wnohang_or_ed_and_keyword_not_reported():
    assert _rule('''
        import os
        from os import WNOHANG

        async def reap(pid):
            os.waitpid(pid, os.WNOHANG | os.WUNTRACED)
            os.waitpid(pid, options=WNOHANG)
    ''', "PYVIBE-011") == []


def test_011_blocking_waitpid_and_system_still_reported():
    v = _rule('''
        import os

        async def reap(pid):
            os.waitpid(pid, 0)
            os.system("make")
    ''', "PYVIBE-011")
    assert [x.severity for x in v] == ["CRITICAL", "CRITICAL"]
    assert v[0].message == "os.waitpid() inside async def blocks the event loop until the child process finishes"


# ── PYVIBE-018: bounded "first free name" search (P014, P078) ──────────────────────

def test_018_p014_fork_name_search_not_reported():
    # backend/app/modules/catalog/maps/service_crud.py:636-646 (geolens-io/geolens)
    assert _rule('''
        async def _generate_fork_name(base, existing_names):
            candidate = f"{base} (copy)"
            if candidate not in existing_names:
                return candidate

            n = 2
            while True:
                candidate = f"{base} (copy {n})"
                if candidate not in existing_names:
                    return candidate
                n += 1
    ''', "PYVIBE-018") == []


def test_018_p078_command_deconfliction_with_break_not_reported():
    # consortium/client/interpreters/interact_agent_interpreter.py:99-122 (not-sekiun/Consortium)
    assert _rule('''
        async def _register_agent_capability_commands(self, agent_capability_command):
            if agent_capability_command.name in self.commands:
                deconfliction_number = 1
                while True:
                    deconflicted_command_name = (
                        agent_capability_command.name + f"_{deconfliction_number}"
                    )
                    if deconflicted_command_name not in self.commands:
                        print_warning("deconflicted")
                        conflicted_command = self.commands.pop(
                            agent_capability_command.name,
                        )
                        conflicted_command.name = deconflicted_command_name
                        self.commands[deconflicted_command_name] = conflicted_command
                        break
                    deconfliction_number += 1
    ''', "PYVIBE-018") == []


def test_018_p006_paging_scan_still_reported_with_bounded_message():
    # backlot/routers/hubspot.py:1076-1089 (brekkylab/backlot), a TP in test-corpus-2
    v = _rule('''
        async def search_objects(conn, body):
            hits: list = []
            cursor = None
            while True:
                batch = store.list_hubspot_objects(conn, after_id=cursor, limit=2000)
                if not batch:
                    break
                cursor = batch[-1]["id"]
                hits += [r for r in batch if _matches(r, body)]
    ''', "PYVIBE-018")
    assert len(v) == 1 and v[0].severity == "CRITICAL"
    assert "indefinitely" not in v[0].message
    assert "until the loop exits" in v[0].message


def test_018_membership_search_with_another_exit_still_reported():
    # A second exit that is not the membership test makes the bound unproven.
    assert len(_rule('''
        async def find(names, ws):
            n = 0
            while True:
                if f"n{n}" not in names:
                    return n
                if ws.closed:
                    break
                n += 1
    ''', "PYVIBE-018")) == 1


# ── PYVIBE-017: empty except BaseException inside a re-raising handler (P043) ───────

def test_017_p043_drain_inside_cancelled_handler_that_reraises_not_reported():
    # backend/app/processing/ingest/tasks_vector.py:226-248 (geolens-io/geolens)
    assert _rule('''
        import asyncio

        async def _heartbeat_service_import_progress(tick):
            try:
                keep_going = await asyncio.shield(tick)
            except asyncio.CancelledError:
                if not tick.done():
                    try:
                        await asyncio.wait_for(asyncio.shield(tick), timeout=5)
                    except asyncio.TimeoutError:
                        log.warning("drain timed out")
                    except BaseException:
                        pass
                raise
    ''', "PYVIBE-017") == []


def test_017_handler_that_does_not_reraise_still_reported():
    v = _rule('''
        import asyncio

        async def run(tick):
            try:
                await tick
            except asyncio.CancelledError:
                try:
                    await cleanup()
                except BaseException:
                    pass
    ''', "PYVIBE-017")
    assert len(v) == 1 and v[0].severity == "CRITICAL"


def test_017_reraise_in_an_outer_function_does_not_cover_a_nested_def():
    assert len(_rule('''
        async def outer():
            try:
                await a()
            except Exception:
                async def inner():
                    try:
                        await b()
                    except BaseException:
                        pass
                await inner()
                raise
    ''', "PYVIBE-017")) == 1


# ── PYVIBE-012: reworded (13 of 22 overstated in test-corpus-2) ───────────────────

def test_012_message_states_weak_reference_not_silent_cancellation():
    v = _rule('''
        import asyncio

        async def handler():
            asyncio.create_task(notify())
    ''', "PYVIBE-012")
    assert len(v) == 1 and v[0].severity == "CRITICAL"
    assert "silently cancelled" not in v[0].message
    assert "weak reference" in v[0].message
