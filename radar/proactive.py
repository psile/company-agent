"""Unified proactive notification policy."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ProactiveDecision:
    decision: str
    score: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


async def evaluate_proactive_notification(
    user_id: str,
    candidate: dict[str, Any],
    conversation_profile: dict[str, Any] | None = None,
    notification_preferences: dict[str, Any] | None = None,
) -> ProactiveDecision:
    return decide_proactive_notification(candidate, conversation_profile, notification_preferences)


def decide_proactive_notification(
    candidate: dict[str, Any],
    conversation_profile: dict[str, Any] | None = None,
    notification_preferences: dict[str, Any] | None = None,
) -> ProactiveDecision:
    profile = conversation_profile or {}
    prefs = notification_preferences or {}
    relevance = _ratio(candidate.get("relevance", candidate.get("score", 0)))
    novelty = _ratio(candidate.get("novelty", 0.75))
    preference = _ratio(candidate.get("user_preference", 0.7))
    goal_match = _ratio(candidate.get("current_goal_match", candidate.get("goal_match", 0.5)))
    source_quality = _ratio(candidate.get("source_quality", 0.7))
    duplicate = _ratio(candidate.get("duplicate_score", 0))
    interrupt = _ratio(candidate.get("interrupt_cost", 0.2))
    urgency = _ratio(candidate.get("urgency", 0))

    score = (
        0.30 * relevance
        + 0.20 * novelty
        + 0.20 * preference
        + 0.15 * goal_match
        + 0.15 * source_quality
        + 0.08 * urgency
        - 0.25 * duplicate
        - 0.15 * interrupt
    )
    level = profile.get("proactive_level", "medium")
    score += {"low": -0.12, "medium": 0.0, "high": 0.08}.get(level, 0.0)
    score = round(max(0.0, min(1.0, score)), 3)
    push_threshold = float(prefs.get("instant_threshold") or 85) / 100
    if not prefs.get("instant", True) or level == "low":
        decision = "digest" if score >= 0.55 else "ignore"
    elif score >= push_threshold:
        decision = "push_now"
    elif score >= 0.55:
        decision = "digest"
    else:
        decision = "ignore"
    return ProactiveDecision(
        decision=decision,
        score=score,
        reason=f"相关性 {relevance:.0%}，目标匹配 {goal_match:.0%}，重复与打扰成本已扣除",
    )


def _ratio(value: Any) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, number / 100 if number > 1 else number))
