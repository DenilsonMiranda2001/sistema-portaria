import argparse
import logging
import os
import signal
import time

from database.connection import conectar_dedicado
from .monitor import reconcile_hardware_incidents
from .worker import dispatch_claimed_commands

logger = logging.getLogger(__name__)
_STOP = False
_LOCK_ID = 184467


def _stop(*_args):
    global _STOP
    _STOP = True


def _tenant_ids():
    conn = conectar_dedicado("controleid-hardware-runtime-tenants")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM condominios ORDER BY id")
            return [row["id"] for row in cur.fetchall()]
    finally:
        conn.close()


def reconcile_incidents_once():
    for tenant_id in _tenant_ids():
        reconcile_hardware_incidents(tenant_id)


def run_forever(registry, *, poll_seconds=2, monitor_seconds=30):
    """Run command dispatch continuously; elect one monitor leader via PostgreSQL advisory lock."""
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    leader = conectar_dedicado("controleid-hardware-monitor-leader")
    with leader.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s) AS acquired", (_LOCK_ID,))
        monitor_leader = bool(cur.fetchone()["acquired"])
    logger.info("hardware runtime started monitor_leader=%s", monitor_leader)
    next_monitor = 0.0
    try:
        while not _STOP:
            dispatch_claimed_commands(registry)
            now = time.monotonic()
            if monitor_leader and now >= next_monitor:
                reconcile_incidents_once()
                next_monitor = now + monitor_seconds
            time.sleep(poll_seconds)
    finally:
        if monitor_leader:
            with leader.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s)", (_LOCK_ID,))
        leader.close()


def main(registry=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if registry is None:
        from .simulator import SimulatorAdapter
        from .adapter import AdapterRegistry
        registry = AdapterRegistry()
        if os.getenv("HARDWARE_SIMULATOR_HTTP_ENABLED", "").lower() in {"1", "true", "yes"}:
            registry.register(SimulatorAdapter())
    if args.once:
        dispatch_claimed_commands(registry)
        reconcile_incidents_once()
        return
    run_forever(registry)


if __name__ == "__main__":
    main()
