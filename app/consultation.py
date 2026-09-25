from __future__ import annotations

import hashlib
import json
import re
from difflib import SequenceMatcher
from typing import Any

from .engine import load_paths

CONSULTATION_VERSION = "2.0.0"

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

WEEKLY_HOURS = {
    "lt3": 2,
    "3_5": 4,
    "5_10": 7,
    "10_20": 14,
    "20_40": 28,
    "40_plus": 40,
}

SCHEDULE_LABELS = {
    "before_work": "before work",
    "after_work": "after work",
    "weekends": "on weekends",
    "daytime": "during the day",
    "flexible": "in flexible blocks",
    "changes": "whenever your changing schedule allows",
}

URGENCY_LABELS = {
    "asap": "as soon as possible",
    "30_days": "within about 30 days",
    "3_months": "within about three months",
    "6_months": "within about six months",
    "1_year": "within about a year",
    "patient": "without forcing a short deadline",
}

FEAR_LABELS = {
    "losing_money": "losing money",
    "wasting_time": "wasting time",
    "failing": "failing publicly or privately",
    "starting_too_late": "starting too late",
    "choosing_wrong": "choosing the wrong direction",
    "not_good_enough": "not being good enough yet",
    "giving_up_stability": "giving up stability too early",
    "others_think": "what other people may think",
    "dont_know_where_start": "not knowing where to start",
}

GOAL_LABELS = {
    "extra_income": "create extra income",
    "new_career": "move into a new career",
    "start_business": "test a business path",
    "work_for_myself": "work more independently",
    "remote_work": "move toward remote work",
    "leave_job_eventually": "build an exit option from your current job",
    "meaningful_work": "move toward more meaningful work",
    "use_experience_differently": "use your existing experience differently",
    "learn_valuable_skill": "build a valuable skill",
    "rebuild_after_setback": "rebuild after a setback",
    "dont_know": "create enough clarity to choose a direction",
}

MODEL_LABELS = {
    "stable_paycheck": "a stable paycheck",
    "freelancing": "freelance work",
    "small_business": "a small business",
    "scalable_business": "a scalable business",
    "selling_products": "selling products",
    "selling_services": "selling services",
    "consulting": "consulting",
    "dont_know": "an open economic model",
}


def _pretty(value: Any) -> str:
    return str(value or "").replace("_", " ").replace("-", " ").title()


def _pick(items: list[str], seed: int, offset: int = 0) -> str:
    return items[(seed + offset) % len(items)]


def _seed_for(answers: dict[str, Any], purchase_id: int, variant: int) -> int:
    payload = json.dumps(answers, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(f"{purchase_id}:{variant}:{payload}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _path_metadata(path_id: str) -> dict[str, Any]:
    for path in load_paths()["paths"]:
        if path["id"] == path_id:
            return path
    return {}


def _score_rows(path: dict[str, Any]) -> list[tuple[str, float]]:
    rows: list[tuple[str, float]] = []
    for key, label in COMPONENT_LABELS.items():
        value = path.get(key)
        if isinstance(value, (int, float)):
            rows.append((label, float(value)))
    return rows


def _top_dimensions(path: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    rows = sorted(_score_rows(path), key=lambda x: x[1], reverse=True)
    return [{"label": label, "score": round(score, 1)} for label, score in rows[:limit]]


def _watch_dimensions(path: dict[str, Any], limit: int = 2) -> list[dict[str, Any]]:
    rows = sorted(_score_rows(path), key=lambda x: x[1])
    return [{"label": label, "score": round(score, 1)} for label, score in rows[:limit]]


def _constraint_focus(answers: dict[str, Any], primary: dict[str, Any]) -> str:
    constraints = set(answers.get("constraints") or [])
    path_constraints = " ".join(primary.get("constraints") or []).lower()
    if "full_time_job" in constraints:
        return "protect your current obligations while you test this"
    if "dependents" in constraints:
        return "avoid a plan that depends on reckless time or income disruption"
    if "limited_startup_money" in constraints or "startup capital" in path_constraints:
        return "prove demand before spending meaningful money"
    if "need_work_from_home" in constraints:
        return "keep the experiment compatible with working from home"
    if "limited_transportation" in constraints:
        return "avoid making transportation a hidden requirement"
    if "limited_computer_access" in constraints:
        return "solve reliable computer access before committing to a computer-heavy path"
    if "limited_internet" in constraints:
        return "keep internet requirements realistic until access improves"
    if "avoid_physical_work" in constraints:
        return "avoid turning the experiment into physically demanding work"
    if "prospecting" in path_constraints:
        return "treat outreach tolerance as a real constraint, not a character flaw"
    return "keep the experiment small enough that evidence can change your mind"


def _tension_read(answers: dict[str, Any], primary: dict[str, Any]) -> str:
    urgency = answers.get("income_urgency")
    model = answers.get("economic_model_preference")
    fear = FEAR_LABELS.get(answers.get("primary_fear"), _pretty(answers.get("primary_fear")).lower())
    family = primary.get("family")

    if urgency in {"asap", "30_days"} and family in {"service_business", "freelance", "knowledge"}:
        return (
            f"You want movement quickly, but this path still requires proof before trust. Your fear of {fear} makes that tension sharper. "
            "The answer is not to force certainty; it is to run a smaller test with a short feedback loop."
        )
    if model == "stable_paycheck" and family != "employment":
        return (
            f"There is a real tension between your preference for {MODEL_LABELS[model]} and a path that carries more independence. "
            f"Because your stated fear is {fear}, this recommendation should begin as a controlled side experiment rather than an identity-level leap."
        )
    if model in {"freelancing", "small_business", "scalable_business", "consulting"} and family == "employment":
        return (
            f"You are drawn toward {MODEL_LABELS.get(model, 'independence')}, yet the strongest immediate path is employment-based. "
            "That is not a contradiction: the employment route can be used as a skill, credibility, and cash-flow bridge rather than a permanent destination."
        )
    return (
        f"Your biggest psychological risk is {fear}. The report should not try to talk you out of that concern. "
        "It should give you an experiment small enough that the result teaches you something before the cost becomes meaningful."
    )


def _first_move(answers: dict[str, Any], primary: dict[str, Any], meta: dict[str, Any], seed: int) -> str:
    family = primary.get("family")
    name = primary.get("name", "this path")
    hours = WEEKLY_HOURS.get(answers.get("weekly_time"), 5)
    sample_count = max(3, min(10, round(hours * 0.8)))
    schedule = SCHEDULE_LABELS.get(answers.get("schedule"), "in your next available block")
    urgency = URGENCY_LABELS.get(answers.get("income_urgency"), "on your current timeline")
    description = meta.get("description", "").rstrip(".")

    if family == "employment":
        variants = [
            f"Use one 30-minute block {schedule} to open {sample_count} current {name} roles. Write down the three requirements that repeat most often, then mark which one you can already prove and which one needs evidence. Do not apply yet; first learn what the market is actually asking for.",
            f"Spend 30 minutes {schedule} comparing {sample_count} live {name} openings. Build a two-column note: 'already credible' and 'must prove'. Your first decision is which missing requirement can be demonstrated fastest, not which course looks most impressive.",
            f"Take 30 minutes {schedule} and inspect {sample_count} real {name} job descriptions. Circle recurring tools, outputs, and experience signals. Choose one signal you can produce evidence for this week. That becomes the first asset in your transition."
        ]
    elif family == "freelance":
        variants = [
            f"Use 30 minutes {schedule} to define one buyer and one narrow outcome for {name}. Then find {sample_count} real examples of people already paying for that outcome. Your goal is to confirm a market before polishing a portfolio.",
            f"Spend 30 minutes {schedule} turning {name} into a one-sentence offer: buyer + problem + deliverable. Compare it against {sample_count} real freelance requests or competitor offers and rewrite it until a stranger could understand what is being bought.",
            f"In one 30-minute block {schedule}, choose the smallest sellable version of {name}. Collect {sample_count} examples of demand, note the language buyers use, and use those words to define your first test offer."
        ]
    elif family == "service_business":
        variants = [
            f"Use 30 minutes {schedule} to choose one customer type for {name}, write one concrete problem you can solve for them, and identify {sample_count} prospects you could realistically reach. Do not build branding or infrastructure yet; prove that the problem earns attention.",
            f"Spend 30 minutes {schedule} reducing {name} to one buyer, one pain point, and one observable result. Find {sample_count} local or online prospects that match. The first signal you need is response, not a logo, website, or business card.",
            f"Take a 30-minute block {schedule} and define a paid pilot for {name}: who it is for, what changes, and what is explicitly not included. Build a list of {sample_count} reachable prospects. Your next step is market contact, not business decoration."
        ]
    else:
        variants = [
            f"Use 30 minutes {schedule} to identify one problem your existing experience could help someone solve through {name}. Write the before-and-after outcome, then list {sample_count} people or communities where that problem already appears. Validate the pain before packaging the knowledge.",
            f"Spend 30 minutes {schedule} turning {name} into one teachable or advisory outcome. Find {sample_count} examples of the audience asking for help with that outcome. Your first evidence should be a repeated problem, not your opinion that the idea is useful.",
            f"In one 30-minute block {schedule}, choose a single outcome for {name} that you can explain from experience. Collect {sample_count} real questions from the intended audience and rank them by frequency. Build from the problem that repeats."
        ]
    move = _pick(variants, seed)
    return f"{move} You are trying to create evidence {urgency}; {_constraint_focus(answers, primary)}. Path context: {description}."


def _week_plan(answers: dict[str, Any], primary: dict[str, Any], meta: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    family = primary.get("family")
    name = primary.get("name", "this path")
    hours = WEEKLY_HOURS.get(answers.get("weekly_time"), 5)
    blocks = max(2, min(8, round(hours / 2)))
    exposure = max(4, min(24, round(hours * 1.5)))
    schedule = SCHEDULE_LABELS.get(answers.get("schedule"), "in your available time")
    urgency = answers.get("income_urgency")
    fast = urgency in {"asap", "30_days"}
    fear = FEAR_LABELS.get(answers.get("primary_fear"), "choosing wrong")

    if family == "employment":
        actions = [
            ("Market map", f"Study {max(6, exposure)} live {name} openings and build a requirement frequency list. Choose one target role variant rather than treating the whole field as one job."),
            ("Proof", f"Use roughly {blocks} focused work blocks {schedule} to create or improve one proof-of-work artifact that demonstrates the most repeated missing requirement."),
            ("Positioning", f"Rewrite your resume/profile around evidence, not adjectives. Then ask {max(2, blocks//2)} people in or near the field for a 15-minute reality check on the artifact and target role."),
            ("Controlled applications", f"Send {max(5, exposure//2)} targeted applications or direct introductions. Track replies, objections, and missing requirements. Continue only if the feedback supports the role hypothesis; otherwise revise the target."),
        ]
    elif family == "freelance":
        actions = [
            ("Offer hypothesis", f"Choose one buyer type and one narrow deliverable for {name}. Review {max(6, exposure)} existing requests or competing offers and write down how buyers describe the problem."),
            ("Credibility asset", f"Use about {blocks} focused blocks {schedule} to build one sample, teardown, before/after example, or mini-case that demonstrates the deliverable without pretending you already have client results."),
            ("Market contact", f"Put the offer in front of {exposure} relevant prospects, communities, or posted opportunities. Keep one message and one offer stable long enough to learn what is actually failing."),
            ("Decision week", f"Review response rate, conversations, objections, and willingness to pay. If nobody cares, change the buyer/problem before changing your entire career direction. If people engage, tighten the offer and seek the first small paid engagement."),
        ]
    elif family == "service_business":
        actions = [
            ("Problem selection", f"Define one customer segment and one costly or annoying problem that {name} can address. Verify it through {max(5, exposure//2)} real customer observations or conversations."),
            ("Pilot design", f"Create the smallest responsible pilot: clear scope, simple price hypothesis, delivery steps, and what success looks like. Limit setup work to about {blocks} focused blocks {schedule}."),
            ("Demand test", f"Reach {exposure} realistic prospects through the channel you can tolerate. Ask for a conversation or pilot, not vague feedback. Record objections exactly as they are stated."),
            ("Evidence review", f"Decide using behavior: replies, calls, pilot interest, and actual willingness to pay. Do not increase spending until the market gives you a reason. If interest exists, refine delivery; if not, revise customer/problem pairing."),
        ]
    else:
        actions = [
            ("Audience problem", f"Choose one audience and collect {max(6, exposure)} real questions related to {name}. Group them into repeated problems and pick the one where your experience gives you the clearest useful point of view."),
            ("Minimum useful asset", f"Use about {blocks} focused blocks {schedule} to create one small useful asset: diagnostic, lesson, outline, template, or short advisory session. It should solve one problem, not display everything you know."),
            ("Live validation", f"Put that asset or session in front of {max(5, exposure//2)} relevant people. Ask what changed, what remained unclear, and whether they would pay for a deeper version."),
            ("Packaging decision", f"Use the feedback to choose between service, training, consulting, or digital-product packaging. Continue only where repeated demand and your delivery energy overlap."),
        ]

    if fast:
        actions[0] = (actions[0][0], actions[0][1] + " Because your timeline is short, finish this stage within the first few days.")
        actions[2] = (actions[2][0], actions[2][1] + " Prioritize direct market contact over additional study.")

    actions[3] = (actions[3][0], actions[3][1] + f" Your fear of {fear} is exactly why this review uses evidence instead of optimism.")
    return [{"week": i + 1, "title": title, "action": action} for i, (title, action) in enumerate(actions)]


def _alternative_analysis(primary: dict[str, Any], alternative: dict[str, Any]) -> dict[str, Any]:
    p_scores = dict(_score_rows(primary))
    a_scores = dict(_score_rows(alternative))
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
    constraints = " ".join(alternative.get("constraints") or []).lower()

    if "income timeline" in constraints or "longer to validate" in constraints:
        switch = "your need for near-term income becomes less urgent"
    elif "capital" in constraints:
        switch = "you can increase the budget available for a controlled test"
    elif "weekly time" in constraints or "learning runway" in constraints:
        switch = "you can consistently free more weekly time"
    elif "prospecting" in constraints:
        switch = "you become willing to do more direct outreach or sales"
    elif "risk" in constraints:
        switch = "your tolerance for uncertainty increases"
    else:
        switch = "one of the constraints holding it back changes materially"

    return {
        "name": alternative.get("name"),
        "score": alternative.get("score"),
        "band": alternative.get("band"),
        "family_label": FAMILY_LABELS.get(alternative.get("family"), _pretty(alternative.get("family"))),
        "upside": f"It has a relative edge on {best_alt}." if best_alt else "It remains credible, but does not clearly dominate the primary path on your strongest factors.",
        "why_below": (
            f"It ranks below {primary.get('name')} mainly because the primary path is stronger on {best_primary}."
            if best_primary
            else f"Its total fit is slightly weaker than {primary.get('name')} across the full profile."
        ),
        "reconsider_if": switch,
    }


def _anti_plan(answers: dict[str, Any], primary: dict[str, Any]) -> list[str]:
    family = primary.get("family")
    constraints = set(answers.get("constraints") or [])
    items = ["Do not confuse more research with progress once the first real-world test is defined."]
    if "full_time_job" in constraints or answers.get("income_urgency") in {"asap", "30_days"}:
        items.append("Do not resign from reliable income merely because this path scored well. Make the path earn that decision with evidence.")
    if family in {"service_business", "freelance", "knowledge"}:
        items.append("Do not spend the first month on branding, legal structure, complex tooling, or a polished website before validating demand.")
    if family == "employment":
        items.append("Do not collect certificates indefinitely. Build evidence that maps to repeated requirements in actual openings.")
    if "limited_startup_money" in constraints:
        items.append("Do not use scarce capital to compensate for uncertainty. Spend only after a test identifies what money would actually unlock.")
    return items[:3]


def _consultation_text(c: dict[str, Any]) -> str:
    chunks = [
        c.get("consultant_read", ""),
        c.get("core_tension", ""),
        c.get("why_primary", ""),
        c.get("first_move", ""),
        " ".join(w.get("action", "") for w in c.get("week_plan", [])),
        " ".join(a.get("why_below", "") + " " + a.get("reconsider_if", "") for a in c.get("alternatives", [])),
        " ".join(c.get("anti_plan", [])),
    ]
    return " ".join(chunks)


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text.lower())).strip()


def similarity(a: str, b: str) -> float:
    a_n, b_n = _normalized(a), _normalized(b)
    if not a_n or not b_n:
        return 0.0
    return SequenceMatcher(None, a_n, b_n).ratio()


def _compose(answers: dict[str, Any], result: dict[str, Any], purchase_id: int, variant: int) -> dict[str, Any]:
    top = result.get("top_paths") or []
    primary = top[0]
    meta = _path_metadata(primary.get("id"))
    seed = _seed_for(answers, purchase_id, variant)

    goals = answers.get("primary_objectives") or ["dont_know"]
    goal_phrase = " and ".join(GOAL_LABELS.get(g, _pretty(g).lower()) for g in goals)
    hours = WEEKLY_HOURS.get(answers.get("weekly_time"), 5)
    schedule = SCHEDULE_LABELS.get(answers.get("schedule"), "in your available time")
    urgency = URGENCY_LABELS.get(answers.get("income_urgency"), "on your current timeline")
    fear = FEAR_LABELS.get(answers.get("primary_fear"), _pretty(answers.get("primary_fear")).lower())
    strengths = _top_dimensions(primary)
    watch = _watch_dimensions(primary)

    openings = [
        f"Here is the decision I would make from your current position: test {primary.get('name')} first, but make it earn the right to become a bigger commitment.",
        f"If this were my decision to structure with your constraints, I would put {primary.get('name')} at the front of the queue and refuse to treat it as a permanent identity yet.",
        f"The strongest move is not to 'choose a life.' It is to give {primary.get('name')} the first controlled test because it currently fits your situation better than the alternatives.",
        f"Your profile does not need another list of possibilities. It needs a priority. Right now, that priority is {primary.get('name')}."
    ]
    opening = _pick(openings, seed)

    consultant_read = (
        f"{opening} You have roughly {hours} hours a week to work with {schedule}, and you want to {goal_phrase} {urgency}. "
        f"The recommendation is strongest on {strengths[0]['label'] if strengths else 'overall fit'} and {strengths[1]['label'] if len(strengths)>1 else 'feasibility'}, "
        f"while the weakest area is {watch[0]['label'] if watch else 'still unproven in the real world'}. "
        f"Your concern about {fear} should shape the size of the experiment, not stop it."
    )

    why_primary = (
        f"{primary.get('name')} ranks first because the combination matters more than any single score: "
        + ", ".join(f"{x['label']} ({x['score']})" for x in strengths)
        + ". "
        + (primary.get("strengths") or ["The path aligns with the strongest parts of your current profile."])[0]
    )

    first_move = _first_move(answers, primary, meta, seed)
    week_plan = _week_plan(answers, primary, meta, seed)
    alternatives = [_alternative_analysis(primary, alt) for alt in top[1:]]

    client_words = (answers.get("twelve_month_change") or "").strip()[:600]
    help_words = (answers.get("help_text") or "").strip()[:500]

    confidence_score = result.get("confidence_score")
    if isinstance(confidence_score, (int, float)) and confidence_score >= 80:
        confidence_note = "There is enough internal consistency in your answers to justify action. That does not make the path certain; it means the next experiment is well founded."
    elif isinstance(confidence_score, (int, float)) and confidence_score >= 60:
        confidence_note = "The direction is usable, but not settled. Your first month matters more than the score because real-world response should either strengthen or weaken the recommendation."
    else:
        confidence_note = "Your answers still contain meaningful ambiguity. Treat this report as a structured hypothesis and use the first month primarily to reduce uncertainty."

    decision_brief = {
        "primary_path": primary.get("name"),
        "why_now": f"It best balances your current fit, constraints, and need to make progress {urgency}.",
        "strongest_advantage": strengths[0]["label"] if strengths else "overall alignment",
        "main_constraint": (primary.get("constraints") or ["No major immediate constraint was detected."])[0],
        "first_move": first_move,
        "thirty_day_target": week_plan[-1]["action"],
    }

    return {
        "version": CONSULTATION_VERSION,
        "consultant_read": consultant_read,
        "core_tension": _tension_read(answers, primary),
        "why_primary": why_primary,
        "first_move": first_move,
        "week_plan": week_plan,
        "alternatives": alternatives,
        "anti_plan": _anti_plan(answers, primary),
        "fit_highlights": strengths,
        "fit_watchouts": watch,
        "decision_brief": decision_brief,
        "confidence_note": confidence_note,
        "client_words": client_words,
        "help_words": help_words,
        "client_snapshot": {
            "current_situation": _pretty(answers.get("current_situation")),
            "primary_goals": [GOAL_LABELS.get(x, _pretty(x)) for x in goals],
            "weekly_time": _pretty(answers.get("weekly_time")),
            "schedule": _pretty(answers.get("schedule")),
            "income_timeline": _pretty(answers.get("income_urgency")),
            "available_capital": _pretty(answers.get("available_capital")),
            "risk_tolerance": _pretty(answers.get("risk_tolerance")),
            "work_location": _pretty(answers.get("work_location")),
            "preferred_model": MODEL_LABELS.get(answers.get("economic_model_preference"), _pretty(answers.get("economic_model_preference"))),
            "primary_fear": FEAR_LABELS.get(answers.get("primary_fear"), _pretty(answers.get("primary_fear"))),
        },
    }


def compose_unique_consultation(
    answers: dict[str, Any],
    result: dict[str, Any],
    purchase_id: int,
    previous_consultation_texts: list[str] | None = None,
) -> dict[str, Any]:
    if not result.get("top_paths"):
        return {"version": CONSULTATION_VERSION, "consultant_read": "The current answers do not create enough signal for a responsible recommendation."}

    previous = [x for x in (previous_consultation_texts or []) if x]
    best: dict[str, Any] | None = None
    best_similarity = 1.0

    for variant in range(16):
        candidate = _compose(answers, result, purchase_id, variant)
        text = _consultation_text(candidate)
        max_sim = max((similarity(text, existing) for existing in previous), default=0.0)
        if max_sim < best_similarity:
            best, best_similarity = candidate, max_sim
        if max_sim < 0.72:
            break

    assert best is not None
    best["originality"] = {
        "max_similarity_to_recent_reports": round(best_similarity, 3),
        "checked_against": len(previous),
        "method": "case-specific synthesis + similarity guard",
    }
    best["fingerprint"] = hashlib.sha256(_consultation_text(best).encode("utf-8")).hexdigest()
    return best


def consultation_text(consultation: dict[str, Any]) -> str:
    return _consultation_text(consultation)
