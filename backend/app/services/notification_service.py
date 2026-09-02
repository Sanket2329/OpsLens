"""
NotificationService — sends Slack notifications (0 tokens, 0 AI calls).

Triggers:
  - Critical/High incident created → alert channel immediately
  - Investigation complete → post summary with confidence + top action

Configuration (in .env):
  SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
  SLACK_ENABLED=true

If SLACK_WEBHOOK_URL is not set, notifications are silently skipped.
"""

import httpx

from app.config.settings import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Severity → Slack color for the attachment sidebar
_SEVERITY_COLORS = {
    "Critical": "#ef4444",   # red
    "High": "#f97316",       # orange
    "Medium": "#eab308",     # yellow
    "Low": "#6b7280",        # grey
}

# Confidence → emoji
_CONFIDENCE_EMOJI = {
    "High": "🟢",
    "Medium": "🟡",
    "Low": "🔴",
}


class NotificationService:

    def __init__(self):
        self._webhook_url = getattr(settings, "slack_webhook_url", "") or ""
        self._enabled = bool(self._webhook_url)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def notify_incident_created(self, incident) -> None:
        """
        Post a Slack alert when a Critical or High severity incident is created.
        Silently skips for Medium/Low.
        """
        if not self._enabled:
            return
        if incident.severity not in ("Critical", "High"):
            return

        color = _SEVERITY_COLORS.get(incident.severity, "#6b7280")

        payload = {
            "attachments": [
                {
                    "color": color,
                    "blocks": [
                        {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": f"🚨 {incident.severity} Incident Created",
                            },
                        },
                        {
                            "type": "section",
                            "fields": [
                                {"type": "mrkdwn", "text": f"*Title:*\n{incident.title}"},
                                {"type": "mrkdwn", "text": f"*Service:*\n{incident.service}"},
                                {"type": "mrkdwn", "text": f"*Severity:*\n{incident.severity}"},
                                {"type": "mrkdwn", "text": f"*Status:*\n{incident.status}"},
                            ],
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"*Description:*\n{incident.description[:400]}{'…' if len(incident.description) > 400 else ''}",
                            },
                        },
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": f"OpsLens · Incident #{incident.id} · Run an investigation to find the root cause",
                                }
                            ],
                        },
                    ],
                }
            ]
        }

        self._send(payload, context=f"incident_created id={incident.id}")

    def notify_investigation_complete(self, investigation_report: dict, incident_title: str) -> None:
        """
        Post a Slack summary when an investigation completes.
        Includes confidence, root cause status, and the first immediate action.
        """
        if not self._enabled:
            return

        confidence = investigation_report.get("confidence", 0)
        confidence_level = investigation_report.get("confidence_level", "Medium")
        root_cause_status = investigation_report.get("root_cause_status", "Likely")
        root_cause = investigation_report.get("root_cause", "See full report")
        executive_summary = investigation_report.get("executive_summary", "")
        actions = investigation_report.get("immediate_actions", [])
        first_action = actions[0] if actions else "See full report"
        inv_id = investigation_report.get("id", "?")
        mode = investigation_report.get("investigation_mode", "standard")
        mode_label = "🧠 CrewAI Deep" if mode == "crew" else "⚡ Quick"

        confidence_emoji = _CONFIDENCE_EMOJI.get(confidence_level, "🟡")

        # Color by confidence
        color = "#22c55e" if confidence >= 75 else "#eab308" if confidence >= 50 else "#ef4444"

        payload = {
            "attachments": [
                {
                    "color": color,
                    "blocks": [
                        {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": f"✅ Investigation Complete — {incident_title[:60]}",
                            },
                        },
                        {
                            "type": "section",
                            "fields": [
                                {"type": "mrkdwn", "text": f"*Confidence:*\n{confidence_emoji} {confidence}% ({confidence_level})"},
                                {"type": "mrkdwn", "text": f"*Root Cause Status:*\n{root_cause_status}"},
                                {"type": "mrkdwn", "text": f"*Mode:*\n{mode_label}"},
                                {"type": "mrkdwn", "text": f"*Investigation ID:*\n#{inv_id}"},
                            ],
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"*Root Cause:*\n{root_cause[:300]}{'…' if len(root_cause) > 300 else ''}",
                            },
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"*First Immediate Action:*\n`{first_action[:200]}`",
                            },
                        },
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": "OpsLens AI Investigation Platform · View full report in the dashboard",
                                }
                            ],
                        },
                    ],
                }
            ]
        }

        self._send(payload, context=f"investigation_complete id={inv_id}")

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _send(self, payload: dict, context: str = "") -> None:
        try:
            response = httpx.post(
                self._webhook_url,
                json=payload,
                timeout=5.0,
            )
            if response.status_code == 200:
                logger.info("Slack notification sent: %s", context)
            else:
                logger.warning(
                    "Slack notification failed: status=%d context=%s",
                    response.status_code,
                    context,
                )
        except Exception as exc:
            # Never let Slack failures affect the main request
            logger.warning("Slack notification error: %s context=%s", exc, context)
