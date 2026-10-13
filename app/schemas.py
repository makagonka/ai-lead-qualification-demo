"""Input, model-output, and response contracts."""
from typing import Literal
from pydantic import BaseModel, Field

class IncomingMessage(BaseModel):
    source: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.:-]+$")
    external_id: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=3, max_length=2500)

class Decision(BaseModel):
    label: Literal["lead", "noise", "needs_review"]
    score: int = Field(ge=0, le=100)
    reason: str = Field(min_length=1, max_length=400)
    draft: str = Field(default="", max_length=1200)

class ReviewRequest(BaseModel):
    action: Literal["approve", "reject"]

class StoredMessage(BaseModel):
    id: int
    source: str
    external_id: str
    text: str
    label: str
    score: int
    reason: str
    draft: str
    review_status: str
    duplicate_of: int | None
    created_at: str
    reused: bool = False
