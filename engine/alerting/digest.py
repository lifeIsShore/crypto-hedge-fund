# engine/alerting/digest.py
"""
Stream 9 — Alerting & Observability

Provides:
  send_digest(step_results)     ← called at end of scheduler run_pipeline()
  send_alert(message)           ← called on individual step failures
  check_heartbeat()             ← called standalone to detect silent pipeline failures

Configuration via environment variables:
  SLACK_WEBHOOK_URL   — Slack incoming webhook (optional)
  SMTP_HOST           — SMTP server for email digest (optional)
  SMTP_PORT           — defaults to 587
  SMTP_USER           — SMTP username / sender address
  SMTP_PASSWORD       — SMTP password
  DIGEST_EMAIL_TO     — comma-separated list of recipient emails

If neither Slack nor SMTP is configured, digest is only logged (not sent).
"""

import os
import logging
import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Slow-step thresholds (seconds). Anything not listed defaults to 300s.
STEP_THRESHOLDS = {
    '1.  Data ingestion':       120,
    '2.  Macro regime refresh': 300,
    '3.  Feature pipeline':      60,
    'W1. PEAD weekly refresh':  300,
    'WE1. ML pipeline refresh': 1800,
}
DEFAULT_STEP_THRESHOLD = 300


# ─────────────────────────────────────────────────────────────────────────────
# SEND ALERT (single message)
# ─────────────────────────────────────────────────────────────────────────────

def send_alert(message: str, level: str = 'critical'):
    """
    Sends a single alert via Slack webhook.
    Always logs at CRITICAL level regardless of whether Slack is configured.
    """
    logger.critical(f"🚨 ALERT [{level.upper()}]: {message}")

    slack_url = os.getenv('SLACK_WEBHOOK_URL', '')
    if not slack_url:
        return

    emoji = {'critical': '🚨', 'warning': '⚠️', 'info': 'ℹ️'}.get(level, '🚨')
    try:
        import urllib.request
        import json as _json
        payload = _json.dumps({'text': f'{emoji} *Hedge Fund Alert*\n{message}'}).encode()
        req = urllib.request.Request(
            slack_url, data=payload,
            headers={'Content-Type': 'application/json'},
        )
        urllib.request.urlopen(req, timeout=5)
        logger.debug("Alert sent to Slack")
    except Exception as e:
        logger.warning(f"Slack alert failed: {e}")


def check_slow_step(step_name: str, elapsed_sec: float):
    """
    Fires a warning alert if a pipeline step exceeded its threshold.
    Called from scheduler._run_step() after each step completes.
    """
    threshold = STEP_THRESHOLDS.get(step_name.strip(), DEFAULT_STEP_THRESHOLD)
    if elapsed_sec > threshold:
        send_alert(
            f"⚠️ Slow step: *{step_name}* took {elapsed_sec:.0f}s "
            f"(threshold {threshold}s)",
            level='warning',
        )


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE DIGEST
# ─────────────────────────────────────────────────────────────────────────────

def send_digest(
    step_results: list,
    date: str = None,
    risk_summary: dict = None,
):
    """
    Sends the end-of-pipeline digest.

    Args:
        step_results: list of dicts with keys:
                        name, status ('success'|'failed'|'skipped'), duration_sec
        date:         pipeline run date (defaults to today)
        risk_summary: optional dict with keys like var_95, regime, portfolio_value_eur,
                      orders_blocked, pre_trade_violations
    """
    if date is None:
        date = str(datetime.date.today())

    text = _build_digest_text(step_results, date, risk_summary)
    logger.info(f"\n{text}")

    _send_via_slack(text)
    _send_via_email(text, date)


def _build_digest_text(step_results: list, date: str, risk_summary: Optional[dict]) -> str:
    """Formats the digest as a human-readable string."""
    lines = [
        f"📊 *Pipeline Summary — {date}*",
        "─" * 42,
    ]

    any_failed = False
    any_slow   = False

    for s in step_results:
        name     = s.get('name', '?')
        status   = s.get('status', '?')
        duration = s.get('duration_sec', 0)

        if status == 'success':
            threshold = STEP_THRESHOLDS.get(name.strip(), DEFAULT_STEP_THRESHOLD)
            if duration > threshold:
                icon = '⚠️ '
                any_slow = True
            else:
                icon = '✅ '
        elif status == 'failed':
            icon = '❌ '
            any_failed = True
        else:
            icon = '⏭️ '

        lines.append(f"  {icon}{name:<32} ({duration:.1f}s)")

    lines.append("─" * 42)

    # Risk summary block
    if risk_summary:
        blocked    = risk_summary.get('orders_blocked', False)
        violations = risk_summary.get('pre_trade_violations', 0)
        var        = risk_summary.get('var_95')
        regime     = risk_summary.get('regime', 'unknown')
        value      = risk_summary.get('portfolio_value_eur')

        lines.append(f"  Orders blocked:       {'🔴 YES' if blocked else '✅ No'}")
        lines.append(f"  Pre-trade violations: {violations}")
        if var is not None:
            lines.append(f"  Portfolio VaR (95%):  {var:.2%}")
        lines.append(f"  Regime:               {regime}")
        if value:
            lines.append(f"  Portfolio value:      €{value:,.0f}")
        lines.append("─" * 42)

    # Summary line
    if any_failed:
        lines.append("  ❌ Pipeline completed WITH FAILURES — check logs")
    elif any_slow:
        lines.append("  ⚠️  Pipeline completed — some steps were slow")
    else:
        lines.append("  ✅ Pipeline completed cleanly")

    return "\n".join(lines)


def _send_via_slack(text: str):
    slack_url = os.getenv('SLACK_WEBHOOK_URL', '')
    if not slack_url:
        return
    try:
        import urllib.request
        import json as _json
        payload = _json.dumps({'text': text}).encode()
        req = urllib.request.Request(
            slack_url, data=payload,
            headers={'Content-Type': 'application/json'},
        )
        urllib.request.urlopen(req, timeout=5)
        logger.info("Digest sent to Slack")
    except Exception as e:
        logger.warning(f"Slack digest failed: {e}")


def _send_via_email(text: str, date: str):
    smtp_host = os.getenv('SMTP_HOST', '')
    smtp_user = os.getenv('SMTP_USER', '')
    recipients_raw = os.getenv('DIGEST_EMAIL_TO', '')

    if not smtp_host or not smtp_user or not recipients_raw:
        return

    recipients = [r.strip() for r in recipients_raw.split(',') if r.strip()]
    if not recipients:
        return

    try:
        import smtplib
        from email.mime.text import MIMEText

        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        smtp_pass = os.getenv('SMTP_PASSWORD', '')

        subject = f"[Hedge Fund] Pipeline Summary — {date}"
        # Strip Slack markdown for plain text email
        plain_text = text.replace('*', '').replace('_', '')

        msg = MIMEText(plain_text, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From']    = smtp_user
        msg['To']      = ', '.join(recipients)

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, recipients, msg.as_string())

        logger.info(f"Digest emailed to {recipients}")
    except Exception as e:
        logger.warning(f"Email digest failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# HEARTBEAT CHECK
# ─────────────────────────────────────────────────────────────────────────────

def check_heartbeat(max_gap_trading_days: int = 2):
    """
    Checks whether the pipeline has run recently.
    Reads pipeline_runs table; alerts if last success is older than
    max_gap_trading_days trading days.

    Run this from a Windows Task Scheduler job or a separate cron:
        python -c "from engine.alerting.digest import check_heartbeat; check_heartbeat()"

    This catches the silent failure case: the .bat doesn't run because of a
    Windows update, login screen, or locked session.
    """
    try:
        from engine.db.db import get_session
        from sqlalchemy import text as sql_text

        session = get_session()
        row = session.execute(sql_text("""
            SELECT MAX(run_date) FROM pipeline_runs
            WHERE status = 'success'
        """)).fetchone()
        session.close()

        if not row or not row[0]:
            send_alert(
                "💀 Heartbeat check: pipeline has NEVER completed successfully. "
                "Check scheduler setup.",
                level='critical',
            )
            return

        last_run = datetime.date.fromisoformat(row[0])
        today    = datetime.date.today()
        gap_days = (today - last_run).days

        # Rough trading day estimate (weekends don't count)
        # We check calendar days with a generous threshold instead of a full
        # trading calendar lookup to keep this dependency-free.
        calendar_threshold = max_gap_trading_days + 3   # +3 for weekends

        if gap_days > calendar_threshold:
            send_alert(
                f"💀 Heartbeat check: pipeline last completed on *{last_run}* "
                f"({gap_days} days ago). Check Windows Task Scheduler or cron.",
                level='critical',
            )
            logger.critical(f"Heartbeat FAIL: last run {last_run} ({gap_days} days ago)")
        else:
            logger.info(f"Heartbeat OK: last successful run {last_run} ({gap_days} days ago)")

    except Exception as e:
        logger.error(f"Heartbeat check failed: {e}")
        send_alert(f"Heartbeat check errored: {e}", level='warning')
