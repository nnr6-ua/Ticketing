from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_employee
from app.db.session import get_db
from app.models import Employee
from app.schemas.ticket import CategoryRead, PriorityRead, SuggestionResponse
from app.services.suggestions import suggest

router = APIRouter(prefix="/suggestions", tags=["suggestions"])


class SuggestionRequest(BaseModel):
    title: str = Field(min_length=0, max_length=120)
    description: str = Field(min_length=0, max_length=5000)


@router.post("", response_model=SuggestionResponse)
def get_suggestion(
    payload: SuggestionRequest,
    db: Session = Depends(get_db),
    _: Employee = Depends(get_current_employee),
) -> SuggestionResponse:
    result = suggest(db, payload.title, payload.description)
    return SuggestionResponse(
        category=CategoryRead.model_validate(result.category),
        priority=PriorityRead.model_validate(result.priority),
        category_is_fallback=result.category_is_fallback,
        priority_is_fallback=result.priority_is_fallback,
    )
