"""
scheduler.py
============

Background auto-refresh scheduler for HoshiyarLahore.

Runs INSIDE the FastAPI process (no external cron needed) so live weather and
historical baselines stay current automatically while the API is running -
whether that's on a laptop during development or once deployed.

WHAT IT DOES
------------
- Refreshes current + 72h forecast weather every REFRESH_MINUTES (default 60).
  Open-Meteo itself updates its forecast roughly hourly, so refreshing more
  often than that gains nothing and just wastes requests.
- Refreshes the 10-year historical baseline once every HISTORICAL_REFRESH_HOURS
  (default 24). Climatological "normals" don't meaningfully change hour to
  hour, so this is intentionally infrequent.
- Runs an immediate refresh once at startup, so the app has current data right
  away instead of waiting a full interval.
- Failures (no internet, Open-Meteo down, etc.) are caught and logged. They
  NEVER crash the server - the API just keeps serving the last good data, and
  the failure is recorded so /api/status can report it honestly.

CONFIGURATION (environment variables, all optional)
----------------------------------------------------
HOSHIYAR_AUTO_REFRESH        "1" (default) or "0" to disable entirely
HOSHIYAR_REFRESH_MINUTES     weather refresh interval in minutes (default 60)
HOSHIYAR_HISTORICAL_HOURS    historical refresh interval in hours (default 24)

IMPORTANT - DEPLOYMENT REQUIREMENT
-----------------------------------
This scheduler only works if the backend runs as a PERSISTENT, always-on
process - e.g. a Render/Railway "Web Service". It will NOT work on serverless
platforms (e.g. Vercel serverless functions, AWS Lambda) because those spin
processes up per-request and don't keep a background thread alive between
requests. This is one reason the plan puts the backend on Render/Railway
(persistent) and only the frontend on Vercel.
"""

from __future__ import annotations

import datetime as dt
import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger("hoshiyar.scheduler")

# In-memory bookkeeping (reset on process restart; /api/status also reads the
# database directly for ground-truth freshness, so a restart doesn't lie).
_last_weather_refresh: dt.datetime | None = None
_last_weather_error: str | None = None
_last_historical_refresh: dt.datetime | None = None
_last_historical_error: str | None = None

_scheduler: BackgroundScheduler | None = None


def _refresh_weather_job() -> None:
    global _last_weather_refresh, _last_weather_error
    try:
        from backend.scripts.refresh_weather import refresh_all_towns
        ok, failed, last_fetch_error = refresh_all_towns()
        if ok == 0:
            # Every town failed - this is NOT a successful refresh, even though
            # refresh_all_towns() itself didn't raise. Record the REAL reason
            # (e.g. a 429 rate limit) rather than guessing "offline" - a wrong
            # guess here is actively misleading when debugging.
            reason = last_fetch_error or "unknown error"
            _last_weather_error = f"all {failed} tehsils failed to fetch: {reason}"
            logger.warning("Auto-refresh: weather refresh failed - %s",
                           _last_weather_error)
        else:
            _last_weather_refresh = dt.datetime.now()
            _last_weather_error = (
                f"{failed} of {ok + failed} tehsils failed: {last_fetch_error}"
                if failed else None
            )
            logger.info("Auto-refresh: weather updated at %s (%d/%d ok)",
                       _last_weather_refresh, ok, ok + failed)
    except Exception as exc:  # noqa: BLE001 - never let the scheduler die
        _last_weather_error = str(exc)
        logger.warning("Auto-refresh: weather refresh failed: %s", exc)


def _refresh_historical_job() -> None:
    global _last_historical_refresh, _last_historical_error
    try:
        from backend.scripts.refresh_historical import refresh_historical
        ok, failed, last_fetch_error = refresh_historical(years=10, start_month=4, end_month=9)
        if ok == 0:
            reason = last_fetch_error or "unknown error"
            _last_historical_error = f"all {failed} tehsils failed to fetch: {reason}"
            logger.warning("Auto-refresh: historical refresh failed - %s",
                           _last_historical_error)
        else:
            _last_historical_refresh = dt.datetime.now()
            _last_historical_error = (
                f"{failed} of {ok + failed} tehsils failed: {last_fetch_error}"
                if failed else None
            )
            logger.info("Auto-refresh: historical baselines updated at %s (%d/%d ok)",
                       _last_historical_refresh, ok, ok + failed)
    except Exception as exc:  # noqa: BLE001
        _last_historical_error = str(exc)
        logger.warning("Auto-refresh: historical refresh failed: %s", exc)


def _historical_table_empty() -> bool:
    """
    Check whether weather_historical currently has any rows. Used to decide
    whether to rebuild historical baselines IMMEDIATELY at startup rather than
    waiting for the daily schedule.

    Why this matters: on hosts with an ephemeral filesystem (e.g. Render/
    Railway free tiers, which wipe local files on every spin-down/restart),
    the SQLite database can come back empty after any restart. Without this
    check, an empty historical table could sit empty for up to
    HOSHIYAR_HISTORICAL_HOURS (default 24h) before the next scheduled rebuild -
    long enough to break the "compared to normal" feature after an idle period.
    If we can't even check (DB not yet initialised), we treat it as empty so
    we attempt to build it rather than silently waiting.
    """
    try:
        from backend.app.db.database import get_connection
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM weather_historical"
            ).fetchone()
            return (row["c"] if row else 0) == 0
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 - table/DB may not exist yet
        return True


def start_scheduler() -> BackgroundScheduler | None:
    """Start the background scheduler. Call once, at FastAPI startup."""
    global _scheduler

    if os.environ.get("HOSHIYAR_AUTO_REFRESH", "1") == "0":
        logger.info("Auto-refresh disabled (HOSHIYAR_AUTO_REFRESH=0)")
        return None

    weather_minutes = int(os.environ.get("HOSHIYAR_REFRESH_MINUTES", "60"))
    historical_hours = int(os.environ.get("HOSHIYAR_HISTORICAL_HOURS", "24"))

    sched = BackgroundScheduler(daemon=True)
    sched.add_job(
        _refresh_weather_job, "interval", minutes=weather_minutes,
        next_run_time=dt.datetime.now(),  # run once immediately, then on interval
        id="weather_refresh", replace_existing=True,
    )

    # Historical baselines normally only rebuild on the slow daily schedule
    # (fetching 10 years of archive data is not cheap). BUT if the table is
    # empty right now - e.g. an ephemeral filesystem wiped it on a cold start -
    # rebuild immediately instead of leaving "compared to normal" broken for
    # up to a day. This runs in the background thread; it does not block the
    # API from serving requests in the meantime.
    #
    # Staggered by 45s after the weather job's immediate run, rather than
    # firing at the exact same instant: two concurrent bursts of requests
    # (5 towns each) hitting Open-Meteo in the same second is an easy way to
    # trip a transient rate limit, especially from a shared/NAT'd IP on a
    # hosting platform's free tier. Letting the weather burst finish first
    # keeps each burst small and separated.
    historical_kwargs = {}
    if _historical_table_empty():
        historical_kwargs["next_run_time"] = dt.datetime.now() + dt.timedelta(seconds=45)
        logger.info("Historical baselines table is empty - scheduling a "
                   "rebuild in 45s instead of waiting for the daily cycle.")

    sched.add_job(
        _refresh_historical_job, "interval", hours=historical_hours,
        id="historical_refresh", replace_existing=True, **historical_kwargs,
    )
    sched.start()
    _scheduler = sched
    logger.info(
        "Auto-refresh started: weather every %sm, historical every %sh",
        weather_minutes, historical_hours,
    )
    return sched


def stop_scheduler() -> None:
    """Stop the scheduler cleanly. Call at FastAPI shutdown."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def trigger_refresh_now() -> dict:
    """Force an immediate weather refresh (used by the manual /api/refresh
    endpoint, e.g. for a demo 'watch it update live' moment)."""
    _refresh_weather_job()
    return refresh_status()


def refresh_status() -> dict:
    """In-memory scheduler bookkeeping: last run times/errors and config."""
    now = dt.datetime.now()

    def age_minutes(t):
        return None if t is None else round((now - t).total_seconds() / 60, 1)

    return {
        "auto_refresh_enabled": os.environ.get("HOSHIYAR_AUTO_REFRESH", "1") != "0",
        "refresh_interval_minutes": int(os.environ.get("HOSHIYAR_REFRESH_MINUTES", "60")),
        "historical_interval_hours": int(os.environ.get("HOSHIYAR_HISTORICAL_HOURS", "24")),
        "weather_last_refreshed": (
            _last_weather_refresh.isoformat() if _last_weather_refresh else None
        ),
        "weather_since_refresh_minutes": age_minutes(_last_weather_refresh),
        "weather_last_error": _last_weather_error,
        "historical_last_refreshed": (
            _last_historical_refresh.isoformat() if _last_historical_refresh else None
        ),
        "historical_since_refresh_minutes": age_minutes(_last_historical_refresh),
        "historical_last_error": _last_historical_error,
    }