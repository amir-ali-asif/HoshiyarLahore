"""
Tests for the request-triggered "refresh if stale" mechanism
(backend/app/scheduler.py: ensure_fresh_weather, _is_weather_stale).

Run with:
    python backend/tests/test_request_triggered_refresh.py
"""

import datetime as dt
import os
import sqlite3
import sys
import tempfile
import threading
import time
from unittest.mock import patch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO_ROOT)

import backend.app.scheduler as sched  # noqa: E402


def _temp_db_with_weather(age_minutes: float | None) -> str:
    """
    A real temp-file SQLite DB (not :memory:) with a single weather_current
    row, aged by `age_minutes` (or no row if age_minutes is None). A real
    file lets each thread open its OWN connection to the same database, just
    like production get_connection() does - :memory: connections are
    thread-affine and would need a shared connection object across threads,
    which doesn't reflect how the real code behaves.
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE weather_current (
            id INTEGER PRIMARY KEY AUTOINCREMENT, town_id TEXT,
            observed_at TEXT, fetched_at TEXT, temperature_c REAL,
            humidity_pct REAL, apparent_temperature_c REAL, wind_speed_kmh REAL
        )"""
    )
    if age_minutes is not None:
        fetched = (dt.datetime.now() - dt.timedelta(minutes=age_minutes)).isoformat(
            timespec="seconds"
        )
        conn.execute(
            "INSERT INTO weather_current (town_id, observed_at, fetched_at, "
            "temperature_c, humidity_pct, apparent_temperature_c, wind_speed_kmh) "
            "VALUES ('t', 'x', ?, 40, 30, 42, 8)",
            (fetched,),
        )
        conn.commit()
    conn.close()
    return path


def _patched_connection(db_path):
    """
    Patch get_connection() to open a FRESH connection to `db_path` on every
    call (mirroring the real function), rather than sharing one connection
    object - so this test accurately reflects production behaviour across
    threads instead of tripping SQLite's thread-affinity guard.
    """
    def _open():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    return patch("backend.app.db.database.get_connection", side_effect=_open)


def test_no_data_is_stale():
    db_path = _temp_db_with_weather(age_minutes=None)
    with _patched_connection(db_path):
        assert sched._is_weather_stale() is True
    os.remove(db_path)


def test_fresh_data_is_not_stale():
    db_path = _temp_db_with_weather(age_minutes=1)
    with _patched_connection(db_path):
        assert sched._is_weather_stale() is False
    os.remove(db_path)


def test_old_data_is_stale():
    db_path = _temp_db_with_weather(age_minutes=sched.STALE_THRESHOLD_MINUTES + 5)
    with _patched_connection(db_path):
        assert sched._is_weather_stale() is True
    os.remove(db_path)


def test_ensure_fresh_weather_skips_when_fresh():
    db_path = _temp_db_with_weather(age_minutes=1)
    with _patched_connection(db_path), \
         patch.object(sched, "_refresh_weather_job") as mock_job:
        sched.ensure_fresh_weather()
        assert not mock_job.called
    os.remove(db_path)


def test_ensure_fresh_weather_refreshes_when_stale():
    db_path = _temp_db_with_weather(age_minutes=sched.STALE_THRESHOLD_MINUTES + 5)
    with _patched_connection(db_path), \
         patch.object(sched, "_refresh_weather_job") as mock_job:
        sched.ensure_fresh_weather()
        assert mock_job.called
        assert mock_job.call_count == 1
    os.remove(db_path)


def test_concurrent_requests_trigger_only_one_refresh():
    """
    The critical safety property: if several requests arrive at once while
    data is stale, only ONE should actually call the refresh job - the
    others must wait for it (via the lock) rather than each independently
    triggering their own fetch, which would recreate the request-burst
    problem that caused an earlier rate-limit issue.
    """
    db_path = _temp_db_with_weather(age_minutes=sched.STALE_THRESHOLD_MINUTES + 5)
    call_count = {"n": 0}

    def slow_refresh_that_updates_the_row():
        # Accurately simulates the real job: takes time, then marks the data
        # fresh - so any thread that checks staleness AFTER this completes
        # correctly sees fresh data and does not refresh again.
        call_count["n"] += 1
        time.sleep(0.3)
        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE weather_current SET fetched_at = ?",
            (dt.datetime.now().isoformat(timespec="seconds"),),
        )
        conn.commit()
        conn.close()

    with _patched_connection(db_path), \
         patch.object(sched, "_refresh_weather_job",
                      side_effect=slow_refresh_that_updates_the_row):
        threads = [threading.Thread(target=sched.ensure_fresh_weather)
                   for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    os.remove(db_path)
    assert call_count["n"] == 1, (
        f"expected exactly 1 refresh from 5 concurrent stale-triggering "
        f"requests, got {call_count['n']}"
    )


def _run_all():
    fns = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR {fn.__name__}: {e}")
    print(f"\n{passed}/{len(fns)} tests passed")
    return passed == len(fns)


if __name__ == "__main__":
    print("Running request-triggered refresh tests...")
    ok = _run_all()
    sys.exit(0 if ok else 1)