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


def _acquire_monitor_leader():
    conn = conectar_dedicado("controleid-hardware-monitor-leader")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s) AS acquired", (_LOCK_ID,))
            if cur.fetchone()["acquired"]:
                return conn
    except Exception:
        conn.close()
        raise
    conn.close()
    return None


def _leader_connection_alive(conn):
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            row = cur.fetchone()
            return bool(row and row["ok"] == 1)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return False


def run_forever(registry, *, poll_seconds=2, monitor_seconds=30):
    """Run command dispatch continuously; elect one monitor leader via PostgreSQL advisory lock."""
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    leader = None
    try:
        leader = _acquire_monitor_leader()
    except Exception as exc:
        logger.error("hardware monitor leader election failed error_type=%s", type(exc).__name__)
    logger.info("hardware runtime started monitor_leader=%s", leader is not None)
    next_monitor = 0.0
    consecutive_failures = 0
    try:
        while not _STOP:
            try:
                dispatch_claimed_commands(registry)
                now = time.monotonic()
                if leader is not None and not _leader_connection_alive(leader):
                    leader = None
                    logger.warning("hardware monitor leadership connection lost")
                if leader is None:
                    try:
                        leader = _acquire_monitor_leader()
                    except Exception as exc:
                        logger.error("hardware monitor leader election failed error_type=%s", type(exc).__name__)
                if leader is not None and now >= next_monitor:
                    reconcile_incidents_once()
                    next_monitor = now + monitor_seconds
                consecutive_failures = 0
                time.sleep(poll_seconds)
            except Exception as exc:
                consecutive_failures += 1
                delay = min(30, poll_seconds * (2 ** min(consecutive_failures, 4)))
                logger.error("hardware runtime cycle failed error_type=%s consecutive_failures=%s retry_seconds=%s",
                             type(exc).__name__, consecutive_failures, delay)
                time.sleep(delay)
    finally:
        if leader is not None:
            try:
                with leader.cursor() as cur:
                    cur.execute("SELECT pg_advisory_unlock(%s)", (_LOCK_ID,))
            finally:
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
