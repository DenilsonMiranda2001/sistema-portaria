from unittest.mock import MagicMock, patch

from hardware.health import database_ready


def _connection_with_row(row):
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = row
    return conn, cursor


def test_database_ready_executes_minimal_probe_and_closes_connection():
    conn, cursor = _connection_with_row({"ok": 1})

    with patch("hardware.health.conectar_dedicado", return_value=conn) as connect:
        assert database_ready() is True

    connect.assert_called_once_with("controleid-hardware-health")
    cursor.execute.assert_called_once_with("SELECT 1 AS ok")
    conn.close.assert_called_once_with()


def test_database_ready_fails_closed_when_probe_result_is_not_expected():
    conn, _ = _connection_with_row({"ok": 0})

    with patch("hardware.health.conectar_dedicado", return_value=conn):
        assert database_ready() is False

    conn.close.assert_called_once_with()


def test_database_ready_fails_closed_and_closes_connection_on_query_error():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.execute.side_effect = RuntimeError("database unavailable")

    with patch("hardware.health.conectar_dedicado", return_value=conn):
        assert database_ready() is False

    conn.close.assert_called_once_with()


def test_database_ready_fails_closed_when_connection_cannot_be_created():
    with patch(
        "hardware.health.conectar_dedicado",
        side_effect=RuntimeError("connection unavailable"),
    ):
        assert database_ready() is False
