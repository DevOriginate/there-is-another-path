from __future__ import annotations
from typing import Any

FAMILY_LABELS = {
    "employment": "Career Path",
    "freelance": "Freelance Path",
    "service_business": "Service Business Path",
    "knowledge": "Knowledge & Expertise Path",
}

COMPONENT_LABELS = {
    "personal_fit": "overall personal fit",
    "market_viability": "market viability",
    "capability_fit": "current capability fit",
    "experience_fit": "experience fit",
    "time_fit": "time and learning runway",
    "financial_fit": "financial feasibility",
    "work_style_fit": "work-style fit",
    "risk_fit": "risk fit",
    "goal_fit": "goal alignment",
    "learning_fit": "learning runway",
}

def _pretty(value: str) -> str:
    return str(value or "").replace("_", " ").replace("-", " ").title()

def _scores(path: dict[str, Any]) -> list[tuple[str, float]]:
    rows: list[tuple[str, float]] = []
    for key, label in COMPONENT_LABELS.items():
        value = path.get(key)
        if isinstance(value, (int, float)):
            rows.append((label, float(value)))
    return rows

def _top_dimensions(path: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    rows = sorted(_scores(path), key=lambda x: x[1], reverse=True)
    return [{"label": label, "score": round(score, 1)} for label, score in rows[:limit]]

def _watch_dimensions(path: dict[str, Any], limit: int = 2) -> list[dict[str, Any]]:
    rows = sorted(_scores(path), key=lambda x: x[1])
    return [{"label": label, "score": round(score, 1)} for label, score in rows[:limit]]

def _switch_condition(path: dict[str, Any]) -> str:
    text = " ".join(path.get("constraints") or []).lower()
    if "income timeline" in text or "longer to validate" in text:
        return "your need for near-term income becomes less urgent."
    if "startup capital" in text or "capital" in text:
        return "you can increase the budget available to test it."
    if "weekly time" in text or "learning runway" in text:
        return "you can consistently free up more weekly time."
    if "risk profile" in text or "risk" in text:
        return "your tolerance for uncertainty increases."
    if "prospecting" in text:
        return "you become comfortable doing more direct outreach or sales."
    if "computer access" in text:
        return "you have reliable computer access."
    if "internet" in text:
        return "you have reliable internet access."
    if "transportation" in text:
        return "your transportation constraint improves."
    if "starting level" in text or "capability" in text:
        return "you strengthen the missing starting capability."
    return "one of your current constraints changes materially in its favor."

def _alternative_analysis(primary: dict[str, Any], alternative: dict[str, Any]) -> dict[str, Any]:
    p_scores = dict(_scores(primary))
    a_scores = dict(_scores(alternative))
    alt_edges = sorted(
        [(label, a_scores[label] - p_scores.get(label, 0)) for label in a_scores],
        key=lambda x: x[1],
        reverse=True,
    )
    primary_edges = sorted(
        [(label, p_scores.get(label, 0) - a_scores[label]) for label in a_scores],
        key=lambda x: x[1],
        reverse=True,
    )
    best_alt = next((label for label, gap in alt_edges if gap >= 4), None)
    best_primary = next((label for label, gap in primary_edges if gap >= 4), None)

    upside = (
        f"It has a relative edge on {best_alt}."
        if best_alt
        else "It remains a credible option, but it does not clearly beat the primary path on your strongest decision factors."
    )
    reason_below = (
        f"It ranks below the primary path mainly because {primary['name']} is stronger on {best_primary}."
        if best_primary
        else f"It ranks below {primary['name']} because the total fit is slightly weaker across the full profile."
    )
    return {
        "name": alternative.get("name"),
        "score": alternative.get("score"),
        "band": alternative.get("band"),
        "family_label": FAMILY_LABELS.get(alternative.get("family"), _pretty(alternative.get("family", "path"))),
        "upside": upside,
        "why_below": reason_below,
        "switch_condition": _switch_condition(alternative),
    }

def _consultant_note(answers: dict[str, Any], primary: dict[str, Any]) -> str:
    fear = _pretty(answers.get("primary_fear", "choosing wrong")).lower()
    return (
        f"Your job is not to prove that {primary['name']} is your forever answer. "
        f"Your job is to collect real evidence. Your stated fear is {fear}; the best response to that fear is a bounded experiment, "
        "not another month of abstract research."
    )

def build_report(answers: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    top = result.get("top_paths", [])
    primary = top[0] if top else None
    if not primary:
        return {
            "headline": "We need more signal before recommending a path.",
            "summary": "Your current answers did not create a strong enough match.",
            "top_paths": [],
        }

    strengths = primary.get("strengths") or []
    constraints = primary.get("constraints") or []
    goals = answers.get("primary_objectives") or ["change"]
    primary_goal = goals[0]
    situation = answers.get("current_situation", "current situation")
    urgency = answers.get("income_urgency", "3_months")

    position = (
        f"You are currently {_pretty(situation).lower()} and your primary objective is "
        f"{_pretty(primary_goal).lower()}. The recommendation weighs your time, capital, risk tolerance, "
        "work preferences, experience, learning runway and income timeline together."
    )

    why = " ".join(strengths[:3]) or "Your overall profile aligns well with the requirements of this path."
    caution = " ".join(constraints[:2]) or "No major immediate constraint was detected."

    urgency_note = {
        "asap": "Because you need income quickly, the first month should favor market feedback over prolonged preparation.",
        "30_days": "Because your income timeline is short, the first month should emphasize validation and direct action.",
        "3_months": "Your timeline allows a balanced mix of skill-building and market validation.",
        "6_months": "Your timeline gives you room to build skill before making a larger transition.",
        "1_year": "You can prioritize durable skill-building over immediate monetization.",
        "patient": "Your patient timeline lets you favor stronger long-term alignment over speed.",
    }.get(urgency, "")

    top_dims = _top_dimensions(primary)
    watch_dims = _watch_dimensions(primary)
    alternatives = [_alternative_analysis(primary, p) for p in top[1:]]

    twelve_month_change = (answers.get("twelve_month_change") or "").strip()
    client_words = twelve_month_change[:600] if twelve_month_change else ""

    snapshot = {
        "current_situation": _pretty(answers.get("current_situation")),
        "primary_goals": [_pretty(x) for x in goals],
        "weekly_time": _pretty(answers.get("weekly_time")),
        "income_timeline": _pretty(answers.get("income_urgency")),
        "available_capital": _pretty(answers.get("available_capital")),
        "risk_tolerance": _pretty(answers.get("risk_tolerance")),
        "work_location": _pretty(answers.get("work_location")),
        "preferred_model": _pretty(answers.get("economic_model_preference")),
    }

    decision_brief = {
        "primary_path": primary["name"],
        "why_now": urgency_note or "This path best matches the balance of fit, feasibility and timing in your current situation.",
        "biggest_advantage": top_dims[0]["label"] if top_dims else "overall fit",
        "biggest_constraint": (constraints[0] if constraints else "No major immediate constraint detected."),
        "first_move": primary["first_move"],
        "thirty_day_target": (primary.get("week_plan") or ["Run the first real-world test and review the evidence."])[-1],
    }

    confidence_score = result.get("confidence_score")
    confidence_band = result.get("confidence_band")
    confidence_explanation = (
        "The signal is strong enough to act on, but the recommendation should still be treated as a real-world experiment."
        if isinstance(confidence_score, (int, float)) and confidence_score >= 80
        else "There is enough signal to choose a direction, but your first month should be used to learn whether the recommendation survives contact with reality."
    )

    return {
        "headline": f"Your strongest next experiment: {primary['name']}",
        "position": position,
        "consultant_note": _consultant_note(answers, primary),
        "client_words": client_words,
        "client_snapshot": snapshot,
        "decision_brief": decision_brief,
        "why_primary": why,
        "caution": caution,
        "timeline_note": urgency_note,
        "fit_highlights": top_dims,
        "fit_watchouts": watch_dims,
        "alternative_analysis": alternatives,
        "confidence": {
            "score": confidence_score,
            "band": confidence_band,
            "explanation": confidence_explanation,
        },
        "conflicts": result.get("conflicts", []),
        "top_paths": [
            {**p, "family_label": FAMILY_LABELS.get(p.get("family"), _pretty(p.get("family", "path")))}
            for p in top
        ],
        "long_term_opportunity": result.get("long_term_opportunity"),
        "first_move": primary["first_move"],
        "week_plan": primary["week_plan"],
        "disclaimer": (
            "This is a decision-support tool, not a guarantee of employment, income, business success, or financial results. "
            "Use the recommendations as experiments and verify requirements for your location and situation."
        ),
    }
