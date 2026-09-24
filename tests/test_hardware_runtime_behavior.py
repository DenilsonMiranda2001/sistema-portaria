from unittest.mock import MagicMock, patch

from hardware import runtime


def test_tenant_ids_queries_all_tenants_and_always_closes_connection():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [{"id": 3}, {"id": 9}]

    with patch("hardware.runtime.conectar_dedicado", return_value=conn) as connect:
        assert runtime._tenant_ids() == [3, 9]

    connect.assert_called_once_with("controleid-hardware-runtime-tenants")
    cursor.execute.assert_called_once_with("SELECT id FROM condominios ORDER BY id")
    conn.close.assert_called_once_with()


def test_monitor_leader_returns_connection_only_when_lock_is_acquired():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = {"acquired": True}

    with patch("hardware.runtime.conectar_dedicado", return_value=conn):
        assert runtime._acquire_monitor_leader() is conn

    cursor.execute.assert_called_once_with(
        "SELECT pg_try_advisory_lock(%s) AS acquired", (runtime._LOCK_ID,)
    )
    conn.close.assert_not_called()


def test_monitor_leader_closes_connection_when_lock_is_not_acquired():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = {"acquired": False}

    with patch("hardware.runtime.conectar_dedicado", return_value=conn):
        assert runtime._acquire_monitor_leader() is None

    conn.close.assert_called_once_with()


def test_monitor_leader_closes_connection_when_election_query_fails():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.execute.side_effect = RuntimeError("database failure")

    with patch("hardware.runtime.conectar_dedicado", return_value=conn):
        try:
            runtime._acquire_monitor_leader()
        except RuntimeError:
            pass
        else:
            raise AssertionError("leader election failure must propagate")

    conn.close.assert_called_once_with()


def test_leader_health_check_closes_broken_connection_and_fails_closed():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.execute.side_effect = RuntimeError("connection lost")

    assert runtime._leader_connection_alive(conn) is False
    conn.close.assert_called_once_with()


def test_leader_health_check_accepts_only_expected_database_probe():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = {"ok": 1}

    assert runtime._leader_connection_alive(conn) is True
    cursor.execute.assert_called_once_with("SELECT 1 AS ok")
    conn.close.assert_not_called()
