"""
Tests for the data fetcher: dedup via fetch_log, rate limiting, retry.
"""
import sqlite3
import time
import pytest
from unittest.mock import patch, MagicMock, call
from app.data.fetcher import (
    is_already_fetched,
    mark_fetched,
    rate_limited_fetch,
    _make_params_hash,
)
from app.database import create_all_tables


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    create_all_tables(path)
    return path


def test_is_already_fetched_returns_false_when_not_fetched(db_path):
    assert not is_already_fetched(db_path, "LeagueDashTeamStats", "2023-24", "abc123")


def test_mark_and_check_fetched(db_path):
    mark_fetched(db_path, "LeagueDashTeamStats", "2023-24", "abc123", 30)
    assert is_already_fetched(db_path, "LeagueDashTeamStats", "2023-24", "abc123")


def test_mark_fetched_is_idempotent(db_path):
    mark_fetched(db_path, "LeagueDashTeamStats", "2023-24", "abc123", 30)
    # Should not raise — INSERT OR IGNORE
    mark_fetched(db_path, "LeagueDashTeamStats", "2023-24", "abc123", 30)
    assert is_already_fetched(db_path, "LeagueDashTeamStats", "2023-24", "abc123")


def test_different_params_hash_not_fetched(db_path):
    mark_fetched(db_path, "LeagueDashTeamStats", "2023-24", "abc123", 30)
    assert not is_already_fetched(db_path, "LeagueDashTeamStats", "2023-24", "xyz789")


def test_params_hash_is_deterministic():
    h1 = _make_params_hash({"season": "2023-24", "type": "Regular Season"})
    h2 = _make_params_hash({"type": "Regular Season", "season": "2023-24"})
    assert h1 == h2  # Order-independent


def test_rate_limited_fetch_sleeps_before_call():
    mock_cls = MagicMock(return_value=MagicMock())
    with patch("app.data.fetcher.time.sleep") as mock_sleep:
        rate_limited_fetch(mock_cls, season="2023-24")
    mock_sleep.assert_called_once()
    sleep_arg = mock_sleep.call_args[0][0]
    assert sleep_arg >= 0.6  # At least the configured sleep


def test_rate_limited_fetch_retries_on_connection_error():
    mock_cls = MagicMock(side_effect=ConnectionError("connection reset"))
    with patch("app.data.fetcher.time.sleep"):
        with pytest.raises(ConnectionError):
            rate_limited_fetch(mock_cls)
    assert mock_cls.call_count == 3  # Max retries


def test_rate_limited_fetch_retries_on_429():
    mock_cls = MagicMock(side_effect=Exception("HTTP 429 Too Many Requests"))
    with patch("app.data.fetcher.time.sleep"):
        with pytest.raises(Exception, match="429"):
            rate_limited_fetch(mock_cls)
    assert mock_cls.call_count == 3


def test_rate_limited_fetch_succeeds_on_second_attempt():
    success = MagicMock()
    mock_cls = MagicMock(side_effect=[ConnectionError("err"), success])
    with patch("app.data.fetcher.time.sleep"):
        result = rate_limited_fetch(mock_cls)
    assert result is success
    assert mock_cls.call_count == 2


def test_rate_limited_fetch_does_not_retry_non_retryable():
    mock_cls = MagicMock(side_effect=ValueError("bad input"))
    with patch("app.data.fetcher.time.sleep"):
        with pytest.raises(ValueError):
            rate_limited_fetch(mock_cls)
    assert mock_cls.call_count == 1  # No retry for non-network errors
