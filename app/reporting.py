from __future__ import annotations

from typing import Any

from .consultation import FAMILY_LABELS


def _pretty(value: str) -> str:
    return str(value or "").replace("_", " ").replace("-", " ").title()


def _legacy_consultation(answers: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Compatibility only for reports created before Consultation V2."""
    top = result.get("top_paths") or []
    primary = top[0] if top else {}
    strengths = primary.get("strengths") or []
    constraints = primary.get("constraints") or []
    return {
        "version": "legacy",
        "consultant_read": (
            f"Your strongest current experiment is {primary.get('name', 'the leading path')}. "
            "This older report was created before the case-specific Consultation V2 composer, so its guidance is less individualized."
        ),
        "core_tension": "Use the recommendation as an experiment rather than a permanent identity decision.",
        "why_primary": " ".join(strengths[:3]) or "The overall profile aligns with this path.",
        "constraint_read": (
            constraints[0] + " Treat that as the first assumption to test rather than a detail to ignore."
            if constraints else
            "No single disqualifying constraint was detected, so the main risk is overconfidence."
        ),
        "first_move": primary.get("first_move", "Define one small real-world test before making a larger commitment."),
        "week_plan": [
            {"week": i + 1, "title": f"Week {i + 1}", "action": text}
            for i, text in enumerate(primary.get("week_plan") or [])
        ],
        "alternatives": [],
        "decision_rules": {
            "continue": "Continue only if the real-world test produces useful evidence.",
            "adjust": "Adjust the experiment when the path is plausible but the execution is not producing signal.",
            "switch": "Re-rank the path when repeated evidence contradicts the recommendation."
        },
        "anti_plan": ["Do not make a major irreversible decision from an older report without testing the recommendation in the real world."],
        "fit_highlights": [],
        "fit_watchouts": [],
        "decision_brief": {
            "primary_path": primary.get("name"),
            "why_now": "It is the strongest result in the saved assessment.",
            "strongest_advantage": strengths[0] if strengths else "overall alignment",
            "main_constraint": constraints[0] if constraints else "No major immediate constraint detected.",
            "first_move": primary.get("first_move", ""),
            "thirty_day_target": (primary.get("week_plan") or ["Review the evidence after 30 days."])[-1],
        },
        "confidence_note": "This report predates the Consultation V2 interpretation layer.",
        "client_words": (answers.get("twelve_month_change") or "")[:600],
        "help_words": (answers.get("help_text") or "")[:500],
        "client_snapshot": {
            "current_situation": _pretty(answers.get("current_situation")),
            "primary_goals": [_pretty(x) for x in answers.get("primary_objectives") or []],
            "weekly_time": _pretty(answers.get("weekly_time")),
            "income_timeline": _pretty(answers.get("income_urgency")),
        },
    }


def build_report(answers: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    top = result.get("top_paths") or []
    primary = top[0] if top else None
    if not primary:
        return {
            "headline": "We need more signal before recommending a path.",
            "summary": "Your current answers did not create a strong enough match.",
            "top_paths": [],
        }

    consultation = result.get("_consultation") or _legacy_consultation(answers, result)
    top_paths = [
        {
            **path,
            "family_label": FAMILY_LABELS.get(path.get("family"), _pretty(path.get("family", "path"))),
        }
        for path in top
    ]

    return {
        "headline": f"Your strongest next experiment: {primary['name']}",
        "consultation_version": consultation.get("version", "2.0.0"),
        "consultant_read": consultation.get("consultant_read", ""),
        "core_tension": consultation.get("core_tension", ""),
        "why_primary": consultation.get("why_primary", ""),
        "constraint_read": consultation.get("constraint_read", ""),
        "decision_brief": consultation.get("decision_brief", {}),
        "client_snapshot": consultation.get("client_snapshot", {}),
        "client_words": consultation.get("client_words", ""),
        "help_words": consultation.get("help_words", ""),
        "fit_highlights": consultation.get("fit_highlights", []),
        "fit_watchouts": consultation.get("fit_watchouts", []),
        "alternative_analysis": consultation.get("alternatives", []),
        "decision_rules": consultation.get("decision_rules", {}),
        "anti_plan": consultation.get("anti_plan", []),
        "first_move": consultation.get("first_move", ""),
        "week_plan": consultation.get("week_plan", []),
        "confidence": {
            "score": result.get("confidence_score"),
            "band": result.get("confidence_band"),
            "explanation": consultation.get("confidence_note", ""),
        },
        "conflicts": result.get("conflicts", []),
        "top_paths": top_paths,
        "long_term_opportunity": result.get("long_term_opportunity"),
        "disclaimer": (
            "This is an automated educational decision-support consultation, not a guarantee of employment, income, clients, "
            "business success, or financial results. It does not replace licensed legal, tax, medical, financial, or other regulated professional advice. "
            "Use the recommendation as a bounded experiment and verify requirements for your location and situation."
        ),
    }
