from __future__ import annotations

import hashlib
import json
import re
from difflib import SequenceMatcher
from typing import Any

from .engine import load_paths

CONSULTATION_VERSION = "2.1.0"
MAX_SIMILARITY = 0.80
MAX_VARIANTS = 128

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
    "changes": "around your changing schedule",
}

URGENCY_LABELS = {
    "asap": "as soon as possible",
    "30_days": "inside the next 30 days",
    "3_months": "inside roughly three months",
    "6_months": "inside roughly six months",
    "1_year": "inside roughly a year",
    "patient": "without forcing a short deadline",
}

FEAR_LABELS = {
    "losing_money": "losing money",
    "wasting_time": "wasting time",
    "failing": "failing",
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

EXPERIENCE_LABELS = {
    "sales": "sales",
    "customer_service": "customer service",
    "management": "management",
    "finance": "finance",
    "technology": "technology",
    "construction": "construction",
    "healthcare": "healthcare",
    "education": "education",
    "logistics": "logistics",
    "manufacturing": "manufacturing",
    "marketing": "marketing",
    "administration": "administration",
    "hospitality": "hospitality",
    "creative": "creative work",
    "legal": "legal work",
    "real_estate": "real estate",
    "transportation": "transportation",
    "retail": "retail",
    "entrepreneurship": "entrepreneurship",
    "other": "other work",
    "none": "no established professional field",
}

_OPENERS = [
    "If I were structuring this decision from your exact position, I would",
    "The cleanest decision from the facts you gave me is to",
    "Your assessment does not need another list of possibilities; it needs a priority, so I would",
    "The strongest move available from your current position is to",
    "I would not ask you to choose a forever identity here. I would",
    "From a consultant's chair, the first move is clear enough to act on: you should",
    "The useful question is not what sounds impressive; it is what deserves the first test. I would",
    "Your constraints narrow the field more than your ambition does. That makes the first decision to",
]

_VERBS = {
    "inspect": ["inspect", "review", "compare", "audit", "map", "study", "scan", "sample"],
    "build": ["build", "assemble", "produce", "draft", "create", "shape", "prepare", "construct"],
    "contact": ["contact", "approach", "reach", "message", "speak with", "put the offer in front of", "test with", "show"],
    "record": ["record", "log", "capture", "write down", "track", "document", "note", "catalog"],
    "decide": ["decide", "judge", "re-rank", "reassess", "review", "choose", "evaluate", "call"],
}

_EVIDENCE = {
    "employment": [
        "recurring requirements",
        "proof employers repeatedly ask for",
        "the skills that appear across real openings",
        "the experience signals that survive across job descriptions",
        "the tools and outputs the market repeats",
        "the difference between nice-to-have and repeated requirements",
    ],
    "freelance": [
        "buyer language",
        "repeated paid requests",
        "the outcomes clients are already asking for",
        "how buyers describe the problem before they know the solution",
        "the deliverables people are already purchasing",
        "what separates a vague skill from a clear paid outcome",
    ],
    "service_business": [
        "a painful customer problem",
        "prospect response",
        "willingness to discuss a pilot",
        "repeated objections",
        "evidence that the problem earns attention",
        "a problem customers already spend time or money trying to solve",
    ],
    "knowledge": [
        "repeated audience questions",
        "a problem your experience can shorten",
        "where people repeatedly ask for guidance",
        "which outcomes your knowledge can make easier",
        "evidence that the audience values the result, not just the information",
        "questions that keep appearing despite free information already existing",
    ],
}


def _pretty(value: Any) -> str:
    return str(value or "").replace("_", " ").replace("-", " ").title()


def _seed_for(answers: dict[str, Any], purchase_id: int, variant: int) -> int:
    payload = json.dumps(answers, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(f"{purchase_id}:{variant}:{payload}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _choice(items: list[str], seed: int, salt: int) -> str:
    return items[(seed // (salt + 1) + salt * 17) % len(items)]


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


def _experience_phrase(answers: dict[str, Any]) -> str:
    areas = [EXPERIENCE_LABELS.get(x, _pretty(x).lower()) for x in answers.get("experience_areas") or [] if x != "none"]
    if not areas:
        return "without relying on an established professional specialty"
    if len(areas) == 1:
        return f"while using your background in {areas[0]}"
    return f"while using your background in {areas[0]} and {areas[1]}"


def _constraint_focus(answers: dict[str, Any], primary: dict[str, Any]) -> tuple[str, str]:
    constraints = set(answers.get("constraints") or [])
    path_constraints = " ".join(primary.get("constraints") or []).lower()
    if "dependents" in constraints:
        return ("family stability", "avoid a test that depends on sudden income or schedule disruption")
    if "full_time_job" in constraints:
        return ("current obligations", "protect your job while you collect evidence outside working hours")
    if "limited_startup_money" in constraints or "startup capital" in path_constraints:
        return ("capital discipline", "make demand prove itself before you spend meaningful money")
    if "need_work_from_home" in constraints:
        return ("location fit", "keep every early test compatible with working from home")
    if "limited_transportation" in constraints:
        return ("transportation", "remove unnecessary travel from the validation plan")
    if "limited_computer_access" in constraints:
        return ("tool access", "solve reliable computer access before making a computer-heavy commitment")
    if "limited_internet" in constraints:
        return ("internet access", "design the test around your actual connectivity rather than ideal conditions")
    if "avoid_physical_work" in constraints:
        return ("physical sustainability", "avoid a path design that quietly depends on physical intensity")
    if "prospecting" in path_constraints:
        return ("sales tolerance", "treat outreach tolerance as a design constraint rather than a personality defect")
    return ("reversibility", "keep the experiment cheap enough that new evidence can change the decision")


def _case_numbers(answers: dict[str, Any], seed: int) -> dict[str, int]:
    hours = WEEKLY_HOURS.get(answers.get("weekly_time"), 5)
    urgency = answers.get("income_urgency")
    urgency_boost = 1.25 if urgency in {"asap", "30_days"} else 1.0 if urgency == "3_months" else 0.85
    market_sample = max(4, min(18, round((hours * 0.75 + (seed % 3)) * urgency_boost)))
    outreach = max(4, min(30, round((hours * 1.35 + ((seed >> 3) % 5)) * urgency_boost)))
    work_blocks = max(2, min(10, round(hours / 2 + ((seed >> 6) % 2))))
    conversations = max(2, min(8, round(hours / 3 + ((seed >> 9) % 2))))
    return {
        "market_sample": market_sample,
        "outreach": outreach,
        "work_blocks": work_blocks,
        "conversations": conversations,
    }


def _tension_read(answers: dict[str, Any], primary: dict[str, Any], seed: int) -> str:
    urgency = answers.get("income_urgency")
    model = answers.get("economic_model_preference")
    fear = FEAR_LABELS.get(answers.get("primary_fear"), _pretty(answers.get("primary_fear")).lower())
    family = primary.get("family")
    focus_name, focus_action = _constraint_focus(answers, primary)
    bridge = _choice(
        [
            "That tension should change the design of the experiment, not become an excuse to stay still.",
            "That conflict is useful because it tells us what the experiment must protect.",
            "That is not a reason to abandon the path; it is a reason to make the test more disciplined.",
            "The contradiction matters only if we ignore it. Here, it becomes a design requirement.",
        ],
        seed,
        5,
    )

    if urgency in {"asap", "30_days"} and family in {"service_business", "freelance", "knowledge"}:
        return (
            f"You want income movement {URGENCY_LABELS[urgency]}, while {primary.get('name')} still needs market proof. "
            f"Your fear of {fear} raises the cost of a vague experiment. {bridge} The practical rule is {focus_action}; "
            f"{focus_name} is the boundary I would not casually violate."
        )
    if model == "stable_paycheck" and family != "employment":
        return (
            f"You prefer {MODEL_LABELS[model]}, yet the strongest current path asks for more independence. "
            f"That is the central tension in this case, especially with your concern about {fear}. {bridge} "
            f"I would preserve {focus_name} and {focus_action} before increasing commitment."
        )
    if model in {"freelancing", "small_business", "scalable_business", "consulting"} and family == "employment":
        return (
            f"Your long-term pull is toward {MODEL_LABELS.get(model, 'independence')}, but the immediate winner is employment-based. "
            f"I would use that route as a bridge for skill, credibility, and cash flow rather than treat it as a permanent identity. "
            f"{bridge} The boundary is simple: {focus_action}."
        )
    return (
        f"The main psychological risk is {fear}; the main operating boundary is {focus_name}. "
        f"{bridge} So the plan is built to {focus_action} while collecting evidence fast enough to justify the next decision."
    )


def _first_move(answers: dict[str, Any], primary: dict[str, Any], meta: dict[str, Any], seed: int) -> str:
    family = primary.get("family")
    name = primary.get("name", "this path")
    numbers = _case_numbers(answers, seed)
    schedule = SCHEDULE_LABELS.get(answers.get("schedule"), "in your next available block")
    evidence = _choice(_EVIDENCE.get(family, _EVIDENCE["employment"]), seed, 7)
    inspect = _choice(_VERBS["inspect"], seed, 11)
    record = _choice(_VERBS["record"], seed, 13)
    focus_name, focus_action = _constraint_focus(answers, primary)
    description = meta.get("description", "").rstrip(".")
    experience = _experience_phrase(answers)

    if family == "employment":
        task = (
            f"Use one 30-minute block {schedule} to {inspect} {numbers['market_sample']} live {name} openings. "
            f"{record.capitalize()} {evidence}, then separate what you can already demonstrate from what still needs proof. "
            f"Pick one missing signal that can be demonstrated this week {experience}."
        )
    elif family == "freelance":
        task = (
            f"Use one 30-minute block {schedule} to {inspect} {numbers['market_sample']} real requests or competing offers around {name}. "
            f"{record.capitalize()} {evidence}, then write a one-sentence offer with one buyer, one problem, and one deliverable. "
            f"Choose the smallest version you could responsibly test {experience}."
        )
    elif family == "service_business":
        task = (
            f"Use one 30-minute block {schedule} to define one buyer for {name} and {inspect} {numbers['market_sample']} examples of that buyer's problem. "
            f"{record.capitalize()} {evidence}, then identify {max(4, numbers['outreach']//2)} reachable prospects. "
            f"Do not build brand assets yet; the first asset is a problem statement that earns a response."
        )
    else:
        task = (
            f"Use one 30-minute block {schedule} to {inspect} {numbers['market_sample']} real questions connected to {name}. "
            f"{record.capitalize()} {evidence}, rank the questions by repetition, and choose one outcome your experience can help shorten. "
            f"The first deliverable is a useful answer to one repeated problem, not a complete knowledge product."
        )

    return (
        f"{task} The rule for this first move is {focus_action}. "
        f"That keeps {focus_name} protected while testing a path whose practical purpose is to {description.lower()}."
    )


def _week_plan(answers: dict[str, Any], primary: dict[str, Any], meta: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    family = primary.get("family")
    name = primary.get("name", "this path")
    numbers = _case_numbers(answers, seed)
    schedule = SCHEDULE_LABELS.get(answers.get("schedule"), "in your available time")
    urgency = answers.get("income_urgency")
    fear = FEAR_LABELS.get(answers.get("primary_fear"), "choosing wrong")
    goal = GOAL_LABELS.get((answers.get("primary_objectives") or ["dont_know"])[0], "create a useful next option")
    focus_name, focus_action = _constraint_focus(answers, primary)
    inspect = _choice(_VERBS["inspect"], seed, 19)
    build = _choice(_VERBS["build"], seed, 23)
    contact = _choice(_VERBS["contact"], seed, 29)
    record = _choice(_VERBS["record"], seed, 31)
    decide = _choice(_VERBS["decide"], seed, 37)
    evidence = _choice(_EVIDENCE.get(family, _EVIDENCE["employment"]), seed, 41)

    if family == "employment":
        stages = [
            ("Define the market target", f"{inspect.capitalize()} {numbers['market_sample']} current {name} openings and {record} {evidence}. Narrow the target to the role variant where your current evidence is closest to repeated demand."),
            ("Build one proof signal", f"Use {numbers['work_blocks']} focused work blocks {schedule} to {build} one proof-of-work asset for the most important missing requirement. The asset must be showable, not just studied."),
            ("Get informed friction", f"{contact.capitalize()} {numbers['conversations']} people in or near the target role and ask where your evidence still looks weak. Update the asset or positioning from repeated criticism, not from one person's taste."),
            ("Run a controlled market test", f"Send {max(5, numbers['outreach']//2)} targeted applications or introductions. {record.capitalize()} replies, silence, objections, and requirement gaps, then {decide} whether the role hypothesis deserves another month."),
        ]
    elif family == "freelance":
        stages = [
            ("Narrow the paid outcome", f"{inspect.capitalize()} {numbers['market_sample']} real buyer requests around {name} and {record} {evidence}. Reduce the offer until a buyer can understand the outcome without needing your biography."),
            ("Create one credibility asset", f"Use {numbers['work_blocks']} focused blocks {schedule} to {build} a sample, teardown, mini-case, or before/after demonstration that proves the deliverable without inventing client results."),
            ("Put the offer in contact with reality", f"{contact.capitalize()} {numbers['outreach']} relevant prospects, communities, or live opportunities using one stable offer long enough to learn. {record.capitalize()} what produces replies and what produces silence."),
            ("Price the evidence, not the fantasy", f"{decide.capitalize()} using response quality, conversations, objections, and willingness to pay. If interest is real, seek the smallest responsible paid engagement; if not, change buyer or problem before abandoning the whole field."),
        ]
    elif family == "service_business":
        stages = [
            ("Choose the expensive annoyance", f"{inspect.capitalize()} {numbers['market_sample']} examples of the customer problem behind {name}. {record.capitalize()} where the problem costs time, money, missed leads, rework, or frustration, and choose one segment to test."),
            ("Design a bounded pilot", f"{build.capitalize()} the smallest responsible pilot in {numbers['work_blocks']} focused blocks {schedule}: clear scope, simple price hypothesis, delivery steps, exclusions, and one observable success condition."),
            ("Ask the market for behavior", f"{contact.capitalize()} {numbers['outreach']} realistic prospects through a channel you can tolerate. Ask for a short conversation or pilot, not compliments. {record.capitalize()} objections word-for-word."),
            ("Earn the right to invest more", f"{decide.capitalize()} from calls, pilot interest, willingness to pay, and delivery feasibility. Spend more only if behavior supports the idea; otherwise revise the customer/problem pairing before adding infrastructure."),
        ]
    else:
        stages = [
            ("Find the repeated question", f"{inspect.capitalize()} {numbers['market_sample']} real questions connected to {name}. Group them by repeated outcome and select the one where your experience gives you the clearest useful shortcut."),
            ("Package one useful result", f"{build.capitalize()} one diagnostic, short lesson, advisory outline, template, or mini-session in {numbers['work_blocks']} focused blocks {schedule}. Solve one problem well instead of displaying everything you know."),
            ("Validate with the intended audience", f"{contact.capitalize()} {max(5, numbers['outreach']//2)} relevant people and ask what changed, what stayed unclear, and whether a deeper version would be worth paying for. {record.capitalize()} repeated language."),
            ("Choose the delivery model", f"{decide.capitalize()} between consulting, training, a service, or a digital asset using demand and your delivery energy. Continue only where the audience's repeated problem overlaps with work you can sustain."),
        ]

    if urgency in {"asap", "30_days"}:
        stages[0] = (stages[0][0], stages[0][1] + " Finish this stage in the first three days because your income timeline does not justify a long research phase.")
        stages[2] = (stages[2][0], stages[2][1] + " Market contact outranks additional study this week.")
    elif urgency in {"1_year", "patient"}:
        stages[1] = (stages[1][0], stages[1][1] + " Your timeline gives you permission to favor durable evidence over speed.")

    stages[3] = (
        stages[3][0],
        stages[3][1]
        + f" This review exists because your fear is {fear}; evidence should carry more weight than optimism. "
        + f"If the month does not move you closer to '{goal}', re-rank the path instead of defending it."
    )

    return [{"week": i + 1, "title": title, "action": action} for i, (title, action) in enumerate(stages)]


def _alternative_analysis(primary: dict[str, Any], alternative: dict[str, Any], seed: int, index: int) -> dict[str, Any]:
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
    best_alt = next((label for label, gap in alt_edges if gap >= 3), None)
    best_primary = next((label for label, gap in primary_edges if gap >= 3), None)
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

    edge_phrase = (
        f"I would keep it visible because its relative advantage is {best_alt}."
        if best_alt
        else _choice(
            [
                "I would keep it as a live backup, but it does not currently dominate a decisive factor.",
                "It is credible enough to preserve, but not strong enough to take the first test slot.",
                "There is real fit here, just not enough to displace the primary path today.",
            ],
            seed,
            47 + index,
        )
    )
    why = (
        f"{primary.get('name')} stays ahead because it is stronger on {best_primary}."
        if best_primary
        else f"{primary.get('name')} holds a small but broader advantage across the full profile."
    )

    return {
        "name": alternative.get("name"),
        "score": alternative.get("score"),
        "band": alternative.get("band"),
        "family_label": FAMILY_LABELS.get(alternative.get("family"), _pretty(alternative.get("family"))),
        "upside": edge_phrase,
        "why_below": why,
        "reconsider_if": switch,
    }


def _anti_plan(answers: dict[str, Any], primary: dict[str, Any], seed: int) -> list[str]:
    family = primary.get("family")
    constraints = set(answers.get("constraints") or [])
    fear = FEAR_LABELS.get(answers.get("primary_fear"), "choosing wrong")
    items = [
        _choice(
            [
                "Do not convert uncertainty into endless research once the first real-world test is defined.",
                "Do not keep studying after you already know what evidence the next decision requires.",
                "Do not mistake preparation for progress once the market-facing experiment is ready.",
                "Do not add another planning layer when the missing information can only come from reality.",
            ],
            seed,
            53,
        )
    ]
    if "full_time_job" in constraints or answers.get("income_urgency") in {"asap", "30_days"}:
        items.append("Do not give up reliable income because a score looks encouraging. Make the path earn a larger commitment through evidence.")
    if family in {"service_business", "freelance", "knowledge"}:
        items.append("Do not spend the first month polishing a brand, legal structure, automation stack, or website while demand is still hypothetical.")
    if family == "employment":
        items.append("Do not collect certificates as a substitute for proof. A smaller artifact tied to repeated job requirements is usually more informative.")
    if "limited_startup_money" in constraints:
        items.append("Do not use scarce capital to buy confidence. Spend only after a test identifies what money would actually unlock.")
    if fear in {"wasting time", "choosing the wrong direction", "failing"}:
        items.append(f"Do not let the fear of {fear} push you into a larger commitment; it is a reason to keep the experiment reversible.")
    return list(dict.fromkeys(items))[:3]


def _consultation_text(c: dict[str, Any]) -> str:
    chunks = [
        c.get("consultant_read", ""),
        c.get("core_tension", ""),
        c.get("why_primary", ""),
        c.get("first_move", ""),
        " ".join(w.get("action", "") for w in c.get("week_plan", [])),
        " ".join(a.get("upside", "") + " " + a.get("why_below", "") + " " + a.get("reconsider_if", "") for a in c.get("alternatives", [])),
        " ".join(c.get("anti_plan", [])),
    ]
    return " ".join(chunks)


def _paragraphs(c: dict[str, Any]) -> list[str]:
    parts = [
        c.get("consultant_read", ""),
        c.get("core_tension", ""),
        c.get("why_primary", ""),
        c.get("first_move", ""),
        *[w.get("action", "") for w in c.get("week_plan", [])],
        *[a.get("upside", "") + " " + a.get("why_below", "") + " " + a.get("reconsider_if", "") for a in c.get("alternatives", [])],
        *c.get("anti_plan", []),
    ]
    return [x for x in parts if x]


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text.lower())).strip()


def similarity(a: str, b: str) -> float:
    a_n, b_n = _normalized(a), _normalized(b)
    if not a_n or not b_n:
        return 0.0
    return SequenceMatcher(None, a_n, b_n).ratio()


def _max_paragraph_similarity(candidate: dict[str, Any], previous_paragraphs: list[str]) -> float:
    if not previous_paragraphs:
        return 0.0
    return max(
        similarity(paragraph, old)
        for paragraph in _paragraphs(candidate)
        for old in previous_paragraphs
    )


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
    focus_name, focus_action = _constraint_focus(answers, primary)
    experience = _experience_phrase(answers)

    opening = _choice(_OPENERS, seed, 2)
    consultant_read = (
        f"{opening} test {primary.get('name')} first and make it earn the right to become a bigger commitment. "
        f"You have roughly {hours} usable hours a week {schedule}; you want to {goal_phrase} {urgency}, {experience}. "
        f"The case is strongest on {strengths[0]['label'] if strengths else 'overall fit'}"
        f"{f' and {strengths[1]["label"]}' if len(strengths) > 1 else ''}, while {watch[0]['label'] if watch else 'real-world validation'} is the area I would watch most closely. "
        f"Your concern about {fear} changes the size of the bet, not the need to test it. The operating boundary is {focus_name}: {focus_action}."
    )

    score_clause = ", ".join(f"{x['label']} ({x['score']})" for x in strengths)
    why_primary = (
        f"{primary.get('name')} ranks first because the combination is stronger than any single trait: {score_clause}. "
        f"{(primary.get('strengths') or ['The path aligns with the strongest parts of your current profile.'])[0]} "
        f"I am treating the score as a prioritization tool, not as proof that the path will work."
    )

    first_move = _first_move(answers, primary, meta, seed)
    week_plan = _week_plan(answers, primary, meta, seed)
    alternatives = [_alternative_analysis(primary, alt, seed, idx) for idx, alt in enumerate(top[1:])]

    client_words = (answers.get("twelve_month_change") or "").strip()[:600]
    help_words = (answers.get("help_text") or "").strip()[:500]

    confidence_score = result.get("confidence_score")
    if isinstance(confidence_score, (int, float)) and confidence_score >= 80:
        confidence_note = "Your answers are internally consistent enough to justify action. That is confidence in the next experiment, not certainty about the final outcome."
    elif isinstance(confidence_score, (int, float)) and confidence_score >= 60:
        confidence_note = "The direction is usable but not settled. The first month should be treated as evidence collection, because real-world response should be allowed to strengthen or weaken the recommendation."
    else:
        confidence_note = "The profile still contains meaningful ambiguity. The report is therefore a structured hypothesis, and the first month should primarily reduce uncertainty rather than increase commitment."

    decision_brief = {
        "primary_path": primary.get("name"),
        "why_now": f"It currently gives the best balance of fit, constraints, and progress toward your goals {urgency}.",
        "strongest_advantage": strengths[0]["label"] if strengths else "overall alignment",
        "main_constraint": (primary.get("constraints") or [f"{focus_name}: {focus_action}."])[0],
        "first_move": first_move,
        "thirty_day_target": week_plan[-1]["action"],
    }

    return {
        "version": CONSULTATION_VERSION,
        "consultant_read": consultant_read,
        "core_tension": _tension_read(answers, primary, seed),
        "why_primary": why_primary,
        "first_move": first_move,
        "week_plan": week_plan,
        "alternatives": alternatives,
        "anti_plan": _anti_plan(answers, primary, seed),
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
    variant_offset: int = 0,
) -> dict[str, Any]:
    if not result.get("top_paths"):
        return {
            "version": CONSULTATION_VERSION,
            "consultant_read": "The current answers do not create enough signal for a responsible recommendation.",
        }

    previous = [x for x in (previous_consultation_texts or []) if x]
    previous_paragraphs = [p for text in previous for p in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text) if len(p) >= 60]
    best: dict[str, Any] | None = None
    best_overall = 1.0
    best_paragraph = 1.0

    for local_variant in range(MAX_VARIANTS):
        variant = variant_offset + local_variant
        candidate = _compose(answers, result, purchase_id, variant)
        text = _consultation_text(candidate)
        overall = max((similarity(text, existing) for existing in previous), default=0.0)
        paragraph = _max_paragraph_similarity(candidate, previous_paragraphs)

        if (overall, paragraph) < (best_overall, best_paragraph):
            best = candidate
            best_overall = overall
            best_paragraph = paragraph

        if overall < MAX_SIMILARITY and paragraph < 0.92:
            best = candidate
            best_overall = overall
            best_paragraph = paragraph
            break

    assert best is not None
    body = _consultation_text(best)
    best["originality"] = {
        "max_similarity_to_recent_reports": round(best_overall, 3),
        "max_paragraph_similarity": round(best_paragraph, 3),
        "checked_against": len(previous),
        "variants_considered": local_variant + 1,
        "method": "case-specific synthesis + whole-report and paragraph similarity guards",
    }
    best["fingerprint"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return best


def consultation_text(consultation: dict[str, Any]) -> str:
    return _consultation_text(consultation)


def consultation_fragment_hashes(consultation: dict[str, Any]) -> list[str]:
    """Non-reversible hashes for the actionable instructions that must never be reused verbatim."""
    fragments = [consultation.get("first_move", "")]
    fragments.extend(item.get("action", "") for item in consultation.get("week_plan", []))
    hashes = []
    for fragment in fragments:
        normalized = _normalized(fragment)
        if normalized:
            hashes.append(hashlib.sha256(normalized.encode("utf-8")).hexdigest())
    return list(dict.fromkeys(hashes))
