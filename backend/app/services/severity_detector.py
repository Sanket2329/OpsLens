"""
SeverityDetector — suggests incident severity from description (0 tokens).

Uses rule-based keyword matching with weighted scoring.
No LLM calls — pure Python regex.

Severity levels and their signals:
  Critical — complete outage, data loss, security breach, all users affected
  High     — major degradation, most users affected, SLA breach
  Medium   — partial degradation, some users affected, workarounds exist
  Low      — minor issue, few users affected, cosmetic bugs
"""

import re
from dataclasses import dataclass

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SeverityDetection:
    suggested_severity: str          # "Critical" | "High" | "Medium" | "Low"
    confidence: float                # 0.0 – 1.0
    signals: list[str]               # Which rules triggered
    reasoning: str                   # Human-readable explanation


# Rule definitions: (pattern, weight, label)
# Higher weight = stronger signal for that severity level
_CRITICAL_RULES = [
    (r"\b(down|outage|unavailable|offline|not responding)\b", 3.0, "service down"),
    (r"\b(all users|everyone|complete(ly)?|entire|100%)\b", 2.5, "all users affected"),
    (r"\b(data.?loss|data.?corrupt|database.?corrupt)\b", 4.0, "data loss/corruption"),
    (r"\b(security.?breach|hack|compromised|unauthorized.?access|exploit)\b", 4.0, "security incident"),
    (r"\b(p0|p1|sev0|sev1|critical|emergency|incident.?1)\b", 2.0, "explicit critical label"),
    (r"\b(payment.*(fail|down|error)|checkout.*fail)\b", 3.0, "payment system failure"),
    (r"\b(production.*down|prod.*outage|prod.*down)\b", 3.5, "production outage"),
    (r"\b(no.*access|cannot.*access|unable.*access)\b", 2.0, "access failure"),
    (r"500\s*(error|status|response)", 2.0, "HTTP 500 errors"),
    (r"\b(crash|crashed|crashing|kernel.?panic)\b", 2.5, "crash"),
]

_HIGH_RULES = [
    (r"\b(slow|latency|timeout|degraded?|performance)\b", 2.0, "performance degradation"),
    (r"\b(most users|majority|large number|significant)\b", 2.0, "most users affected"),
    (r"\b(p2|sev2|high|major)\b", 1.5, "explicit high label"),
    (r"\b(memory.?leak|cpu.?(spike|high|100%)|oom|out.?of.?memory)\b", 2.5, "resource exhaustion"),
    (r"\b(database|db|postgres|mysql|redis|mongo).*(error|fail|slow|down)\b", 2.0, "database issue"),
    (r"\b(deploy|deployment|rollout|release).*(fail|broke|issue|problem)\b", 2.0, "deployment issue"),
    (r"\b(queue|kafka|rabbit|message).*(back(log|up)|full|overflow)\b", 2.0, "queue backlog"),
    (r"\b(api.*(error|fail|timeout)|endpoint.*(fail|slow))\b", 1.5, "API failures"),
    (r"(4[0-9]{2}|5[0-9]{2})\s*(error|status)", 1.5, "HTTP error codes"),
    (r"\b(connection.?(refused|timeout|pool.?exhaust))\b", 2.5, "connection issues"),
]

_MEDIUM_RULES = [
    (r"\b(intermittent|occasional|sometimes|sporadic|flapping)\b", 2.0, "intermittent issue"),
    (r"\b(some users|few users|a few|certain users)\b", 1.5, "limited users affected"),
    (r"\b(p3|sev3|medium|moderate)\b", 1.5, "explicit medium label"),
    (r"\b(retry|retrying|fallback|graceful)\b", 1.0, "retry/fallback in place"),
    (r"\b(warning|warn|elevated|increased)\b", 1.0, "warning signals"),
    (r"\b(workaround|manual|bypass)\b", 1.5, "workaround exists"),
]

_LOW_RULES = [
    (r"\b(cosmetic|ui|display|visual|layout|style)\b", 2.0, "cosmetic issue"),
    (r"\b(typo|spelling|grammar|wording)\b", 2.0, "content issue"),
    (r"\b(minor|small|tiny|trivial)\b", 1.5, "explicit minor label"),
    (r"\b(p4|sev4|low|informational)\b", 1.5, "explicit low label"),
    (r"\b(feature.?request|enhancement|suggestion)\b", 2.0, "not an incident"),
    (r"\b(documentation|docs|readme)\b", 1.5, "documentation issue"),
]

_ALL_RULES = [
    ("Critical", _CRITICAL_RULES),
    ("High", _HIGH_RULES),
    ("Medium", _MEDIUM_RULES),
    ("Low", _LOW_RULES),
]


def detect_severity(title: str, description: str) -> SeverityDetection:
    """
    Analyse incident title + description and suggest a severity level.

    Returns a SeverityDetection with the suggestion, confidence (0-1),
    the signals that triggered, and a human-readable explanation.
    """
    combined = f"{title} {description}".lower()

    scores: dict[str, float] = {"Critical": 0.0, "High": 0.0, "Medium": 0.0, "Low": 0.0}
    all_signals: dict[str, list[str]] = {"Critical": [], "High": [], "Medium": [], "Low": []}

    for severity, rules in _ALL_RULES:
        for pattern, weight, label in rules:
            if re.search(pattern, combined, re.IGNORECASE):
                scores[severity] += weight
                all_signals[severity].append(label)

    # Find the winning severity
    best = max(scores, key=lambda s: scores[s])
    best_score = scores[best]

    # If no signals fired at all, default to Medium
    if best_score == 0:
        return SeverityDetection(
            suggested_severity="Medium",
            confidence=0.3,
            signals=[],
            reasoning="No strong severity signals detected. Defaulting to Medium.",
        )

    # Compute confidence: ratio of best score to total
    total = sum(scores.values())
    confidence = min(best_score / max(total, 1), 0.95)

    triggered_signals = all_signals[best]
    other_signals = [
        f"{sev}: {', '.join(sigs)}"
        for sev, sigs in all_signals.items()
        if sev != best and sigs
    ]

    reasoning_parts = [f"Detected {best} signals: {', '.join(triggered_signals)}."]
    if other_signals:
        reasoning_parts.append(f"Also noted: {'; '.join(other_signals)}.")

    logger.info(
        "Severity detected: %s (confidence=%.2f) signals=%s",
        best,
        confidence,
        triggered_signals,
    )

    return SeverityDetection(
        suggested_severity=best,
        confidence=round(confidence, 2),
        signals=triggered_signals,
        reasoning=" ".join(reasoning_parts),
    )
