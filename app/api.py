"""Read-only/outbox-free demonstration API. Bind to localhost; no authentication."""
import os
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException
from app.classification import Classifier, OfflineClassifier, OpenAIClassifier, quick_filter
from app.schemas import IncomingMessage, Decision, StoredMessage, ReviewRequest
from app.storage import Store

def create_app(db_path: str | Path | None = None, classifier: Classifier | None = None) -> FastAPI:
    api = FastAPI(title="AI Lead Qualification Demo", version="1.0.0")
    store = Store(db_path or os.getenv("DEMO_DB_PATH", "./data/demo.sqlite3"))
    if classifier is None:
        mode = os.getenv("DEMO_MODE", "offline").casefold()
        if mode not in ("offline", "openai"):
            raise ValueError("DEMO_MODE must be offline or openai")
        classifier = OpenAIClassifier() if mode == "openai" else OfflineClassifier()

    @api.get("/health")
    def health() -> dict[str,str]:
        return {"status": "ok"}

    @api.post("/v1/messages", response_model=StoredMessage)
    def receive(payload: IncomingMessage) -> StoredMessage:
        row, created = store.insert(payload)
        if not created or row.label == "duplicate":
            return row
        excluded = quick_filter(payload.text)
        if excluded:
            return store.finish(row.id, Decision(label="noise",score=0,reason=excluded))
        try:
            assert classifier is not None
            decision = classifier.classify(payload.text)
        except Exception:
            # Safe fallback; does not expose keys, tokens or provider error strings.
            decision = Decision(label="needs_review",score=0,reason="Classifier unavailable; manual review required")
        if decision.label != "lead":
            decision.draft = ""
        return store.finish(row.id, decision)

    @api.get("/v1/messages", response_model=list[StoredMessage])
    def list_messages(label: Literal["lead","noise","needs_review","duplicate"] | None = None):
        return store.list_items(label)

    @api.get("/v1/messages/{item_id}", response_model=StoredMessage)
    def get_message(item_id: int):
        result = store.get(item_id)
        if result is None:
            raise HTTPException(404, "Message not found")
        return result

    @api.post("/v1/messages/{item_id}/review", response_model=StoredMessage)
    def review(item_id: int, body: ReviewRequest):
        if store.get(item_id) is None:
            raise HTTPException(404, "Message not found")
        try:
            return store.review(item_id, body.action)
        except ValueError as error:
            raise HTTPException(409,str(error)) from error

    return api

app = create_app()
