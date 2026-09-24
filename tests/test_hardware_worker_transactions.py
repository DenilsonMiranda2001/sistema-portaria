from unittest.mock import Mock, patch

import pytest

from hardware.worker import claim_command_batch, finish_dispatched_command


def test_claim_batch_commits_and_releases_after_repository_work():
    conn = Mock()
    repo = Mock()
    repo.claim_pending_commands.return_value = [{"id": "command-1"}]

    with patch("hardware.worker.conectar", return_value=conn), \
         patch("hardware.worker.liberar") as release, \
         patch("hardware.worker.HardwareRepository", return_value=repo):
        result = claim_command_batch(20)

    assert result == [{"id": "command-1"}]
    repo.recover_stuck_commands.assert_called_once_with()
    repo.expire_commands.assert_called_once_with()
    repo.claim_pending_commands.assert_called_once_with(20)
    conn.commit.assert_called_once_with()
    conn.rollback.assert_not_called()
    release.assert_called_once_with(conn)


def test_claim_batch_rolls_back_and_releases_on_repository_failure():
    conn = Mock()
    repo = Mock()
    repo.expire_commands.side_effect = RuntimeError("database failure")

    with patch("hardware.worker.conectar", return_value=conn), \
         patch("hardware.worker.liberar") as release, \
         patch("hardware.worker.HardwareRepository", return_value=repo):
        with pytest.raises(RuntimeError, match="database failure"):
            claim_command_batch(20)

    conn.commit.assert_not_called()
    conn.rollback.assert_called_once_with()
    release.assert_called_once_with(conn)
    repo.claim_pending_commands.assert_not_called()


def test_finish_command_commits_and_releases_short_transaction():
    conn = Mock()
    repo = Mock()

    with patch("hardware.worker.conectar", return_value=conn), \
         patch("hardware.worker.liberar") as release, \
         patch("hardware.worker.HardwareRepository", return_value=repo):
        finish_dispatched_command(
            "command-1", succeeded=False, error="adapter_rejected",
            retry_seconds=10, retryable=True,
        )

    repo.finish_command.assert_called_once_with(
        "command-1", succeeded=False, error="adapter_rejected",
        retry_seconds=10, retryable=True,
    )
    conn.commit.assert_called_once_with()
    conn.rollback.assert_not_called()
    release.assert_called_once_with(conn)


def test_finish_command_rolls_back_and_releases_on_failure():
    conn = Mock()
    repo = Mock()
    repo.finish_command.side_effect = RuntimeError("write failure")

    with patch("hardware.worker.conectar", return_value=conn), \
         patch("hardware.worker.liberar") as release, \
         patch("hardware.worker.HardwareRepository", return_value=repo):
        with pytest.raises(RuntimeError, match="write failure"):
            finish_dispatched_command("command-1", succeeded=True)

    conn.commit.assert_not_called()
    conn.rollback.assert_called_once_with()
    release.assert_called_once_with(conn)
