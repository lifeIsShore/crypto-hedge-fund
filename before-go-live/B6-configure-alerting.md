# B6: Configure Alerting (Slack / Email)
**Blocker: 6 of 7 | File: `.env`**

---

## What is wrong

The alerting system in `engine/alerting/digest.py` is fully built and correct.
It supports both Slack webhooks and SMTP email. The end-of-pipeline digest,
individual step failure alerts, slow-step warnings, and heartbeat checks all
call `send_alert()` or `send_digest()`.

But the `.env` has:
```
SLACK_WEBHOOK_URL=
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
DIGEST_EMAIL_TO=
```

Every field is blank. `digest.py` checks for these and silently does nothing
if they're missing:
```python
slack_url = os.getenv('SLACK_WEBHOOK_URL', '')
if not slack_url:
    return   # silent no-op
```

**Consequence:** The pipeline can crash at step 4 at 3am. You wake up,
check the dashboard, see stale data from yesterday, and have no idea
when or why it stopped. This is the "Silent Killer" identified in your
own `missing-parts.md`.

---

## Fix — Option A: Slack (Recommended, 10 minutes)

1. Go to https://api.slack.com/apps
2. Create a new app → "From scratch" → pick your workspace
3. Go to "Incoming Webhooks" → Activate → "Add New Webhook to Workspace"
4. Pick a channel (e.g. `#hedge-fund-alerts`)
5. Copy the webhook URL (looks like `https://hooks.slack.com/services/T.../B.../...`)
6. Add to `.env`:
```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

That's it. The digest will now send a full pipeline summary every day at
the end of the pipeline run, and individual step failures will send
immediate alerts.

---

## Fix — Option B: Email via Gmail SMTP (15 minutes)

1. Enable 2FA on your Google account
2. Go to https://myaccount.google.com/apppasswords
3. Create an App Password for "Mail"
4. Add to `.env`:
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your.email@gmail.com
SMTP_PASSWORD=your-16-char-app-password
DIGEST_EMAIL_TO=your.email@gmail.com
```

---

## Fix — Heartbeat check (Critical addition)

The `check_heartbeat()` function in `digest.py` is built but not scheduled.
It detects if the pipeline stopped running without anyone noticing.

Add this to Windows Task Scheduler to run every morning at 9am:

1. Open Task Scheduler → Create Basic Task
2. Name: `HedgeFund Heartbeat`
3. Trigger: Daily at 09:00
4. Action: Start a program
   - Program: `python`
   - Arguments: `-c "from engine.alerting.digest import check_heartbeat; check_heartbeat()"`
   - Start in: `C:\Users\ahmty\Desktop\hedge-fund`
5. Save

This will send you a Slack/email alert if the pipeline hasn't run in 2+ trading
days — catches the "Windows update restarted my PC and the .bat never ran" case.

---

## Test after setup

Run this to confirm alerting works before going live:
```bash
cd C:\Users\ahmty\Desktop\hedge-fund
python -c "from engine.alerting.digest import send_alert; send_alert('Test alert — system online', level='info')"
```

You should receive the message in Slack or email within 10 seconds.
