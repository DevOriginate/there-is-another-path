from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from . import db
from .access import active_purchase
from .models import validate_free_text

APP_DIR = Path(__file__).resolve().parent
router = APIRouter()


def _question_map() -> dict[str, dict]:
    schema = json.loads((APP_DIR / "data" / "questions.json").read_text(encoding="utf-8"))
    return {q["id"]: q for q in schema["questions"]}


def _sanitize_draft_answers(answers: dict) -> dict:
    if not isinstance(answers, dict):
        raise HTTPException(400, "Draft answers must be an object")
    if len(json.dumps(answers)) > 20000:
        raise HTTPException(413, "Draft is too large")

    question_map = _question_map()
    clean: dict[str, Any] = {}
    for key, value in answers.items():
        question = question_map.get(key)
        if not question:
            continue

        qtype = question.get("type")
        if qtype == "text":
            clean[key] = validate_free_text(str(value or "")[:1500])
        elif qtype == "multi":
            if isinstance(value, list):
                clean[key] = [str(v)[:100] for v in value[:20]]
        elif qtype == "scale_1_5":
            try:
                number = int(value)
            except (TypeError, ValueError):
                continue
            if 1 <= number <= 5:
                clean[key] = number
        elif qtype == "forced_pairs":
            if isinstance(value, dict):
                clean[key] = {
                    str(k)[:20]: str(v)[:100]
                    for k, v in list(value.items())[:10]
                }
        else:
            clean[key] = str(value)[:100]

    return clean


class DraftPayload(BaseModel):
    answers: dict = Field(default_factory=dict)
    current_index: int = Field(default=0, ge=0, le=100)


@router.get("/api/v1/assessments/draft")
def get_assessment_draft(request: Request):
    purchase = active_purchase(request)
    if db.get_assessment_for_purchase(purchase["id"]):
        return {"answers": {}, "current_index": 0, "completed": True}

    draft = db.get_assessment_draft(purchase["id"])
    if not draft:
        return {"answers": {}, "current_index": 0, "completed": False}

    return {
        "answers": draft["answers"],
        "current_index": draft["current_index"],
        "completed": False,
    }


@router.post("/api/v1/assessments/draft")
def save_assessment_draft(request: Request, payload: DraftPayload):
    purchase = active_purchase(request)
    if db.get_assessment_for_purchase(purchase["id"]):
        raise HTTPException(409, "Assessment is already completed")

    answers = _sanitize_draft_answers(payload.answers)
    db.save_assessment_draft(purchase["id"], answers, payload.current_index)
    return {"ok": True}
