from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, Priority
from app.services.catalogs import resolve_default_category, resolve_default_priority


@dataclass(frozen=True)
class Suggestion:
    category: Category
    priority: Priority
    category_is_fallback: bool
    priority_is_fallback: bool


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.lower())
    without_marks = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", " ", without_marks).strip()


def _keyword_score(text: str, keywords: list[str] | None) -> int:
    score = 0
    for keyword in keywords or []:
        normalized = _normalize(keyword.strip())
        if not normalized:
            continue
        if " " in normalized:
            if normalized in text:
                score += 2
        elif re.search(rf"\b{re.escape(normalized)}\b", text):
            score += 1
    return score


def _pick(
    db: Session,
    model: type[Category] | type[Priority],
    text: str,
    fallback,
):
    candidates = db.scalars(
        select(model)
        .where(model.is_active.is_(True), model.is_system.is_(False))
        .order_by(model.sort_order, model.id)
    ).all()

    best = None
    best_score = 0
    for candidate in candidates:
        score = _keyword_score(text, candidate.keywords)  # type: ignore[attr-defined]
        if score > best_score:
            best = candidate
            best_score = score
        elif score == best_score and score > 0 and best is not None:
            if (candidate.sort_order, candidate.id) < (best.sort_order, best.id):
                best = candidate

    if best is None:
        return fallback, True
    return best, False


def suggest(db: Session, title: str, description: str) -> Suggestion:
    text = _normalize(f"{title} {description}")
    category, category_is_fallback = _pick(
        db, Category, text, resolve_default_category(db)
    )
    priority, priority_is_fallback = _pick(
        db, Priority, text, resolve_default_priority(db)
    )
    return Suggestion(
        category=category,
        priority=priority,
        category_is_fallback=category_is_fallback,
        priority_is_fallback=priority_is_fallback,
    )
