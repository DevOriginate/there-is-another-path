from __future__ import annotations
from typing import Any

FAMILY_LABELS = {
    "employment": "Career Path",
    "freelance": "Freelance Path",
    "service_business": "Service Business Path",
    "knowledge": "Knowledge & Expertise Path",
}

def _pretty(value: str) -> str:
    return value.replace('_', ' ').replace('-', ' ').title()

def build_report(answers: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    top = result.get('top_paths', [])
    primary = top[0] if top else None
    if not primary:
        return {"headline":"We need more signal before recommending a path.","summary":"Your current answers did not create a strong enough match.","top_paths":[]}
    strengths = primary.get('strengths') or []
    constraints = primary.get('constraints') or []
    primary_goal = (answers.get('primary_objectives') or ['change'])[0]
    situation = answers.get('current_situation', 'current situation')
    urgency = answers.get('income_urgency', '3_months')
    position = (
        f"You are currently {_pretty(situation).lower()} and your primary objective is "
        f"{_pretty(primary_goal).lower()}. The engine prioritized paths that fit your available time, "
        f"capital, work preferences and current income timeline."
    )
    why = " ".join(strengths[:3]) or "Your overall profile aligns well with the requirements of this path."
    caution = " ".join(constraints[:2]) or "No major immediate constraint was detected."
    urgency_note = {
        'asap': 'Because you need income quickly, the first month focuses on testing market response rather than prolonged training.',
        '30_days': 'Because your income timeline is short, the first month emphasizes validation and direct action.',
        '3_months': 'Your timeline allows a balance of learning and market validation.',
        '6_months': 'Your timeline gives you room to build skill before making a larger transition.',
        '1_year': 'You can afford to prioritize durable skill-building over immediate monetization.',
        'patient': 'Your patient timeline allows the engine to favor stronger long-term alignment.'
    }.get(urgency, '')
    return {
        "headline": f"Your strongest next experiment: {primary['name']}",
        "position": position,
        "why_primary": why,
        "caution": caution,
        "timeline_note": urgency_note,
        "confidence": {"score": result.get('confidence_score'), "band": result.get('confidence_band')},
        "conflicts": result.get('conflicts', []),
        "top_paths": [{**p, "family_label": FAMILY_LABELS.get(p.get('family'), _pretty(p.get('family','path')))} for p in top],
        "long_term_opportunity": result.get('long_term_opportunity'),
        "first_move": primary['first_move'],
        "week_plan": primary['week_plan'],
        "disclaimer": "This is a decision-support tool, not a guarantee of employment, income, business success, or financial results. Use the recommendations as experiments and verify requirements for your location and situation."
    }
