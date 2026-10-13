"""SQLite storage with idempotency and cross-source normalized-content deduplication."""
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from app.schemas import IncomingMessage, Decision, StoredMessage

def normalize_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.casefold().split()).encode("utf-8")).hexdigest()

class Store:
    def __init__(self, db_path: str | Path):
        self.path = str(db_path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    text_hash TEXT NOT NULL,
                    label TEXT NOT NULL DEFAULT 'processing',
                    score INTEGER NOT NULL DEFAULT 0,
                    reason TEXT NOT NULL DEFAULT 'Waiting for classifier',
                    draft TEXT NOT NULL DEFAULT '',
                    review_status TEXT NOT NULL DEFAULT 'not_required',
                    duplicate_of INTEGER REFERENCES messages(id),
                    created_at TEXT NOT NULL,
                    UNIQUE(source, external_id)
                );
                CREATE INDEX IF NOT EXISTS idx_message_hash ON messages(text_hash);
                CREATE INDEX IF NOT EXISTS idx_message_label ON messages(label);
            """)

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def as_record(row: sqlite3.Row, reused: bool = False) -> StoredMessage:
        return StoredMessage(**dict(row), reused=reused)

    def insert(self, incoming: IncomingMessage) -> tuple[StoredMessage, bool]:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            exists = db.execute("SELECT * FROM messages WHERE source=? AND external_id=?", (incoming.source, incoming.external_id)).fetchone()
            if exists:
                return self.as_record(exists, reused=True), False
            digest = normalize_hash(incoming.text)
            duplicate = db.execute("SELECT id FROM messages WHERE text_hash=? ORDER BY id LIMIT 1", (digest,)).fetchone()
            dupe_id = int(duplicate["id"]) if duplicate else None
            cursor = db.execute(
                """INSERT INTO messages (source,external_id,text,text_hash,label,reason,duplicate_of,created_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (incoming.source, incoming.external_id, incoming.text, digest,
                 "duplicate" if dupe_id else "processing",
                 "Repeated normalized content" if dupe_id else "Waiting for classifier",
                 dupe_id, datetime.now(timezone.utc).isoformat()),
            )
            row = db.execute("SELECT * FROM messages WHERE id=?", (cursor.lastrowid,)).fetchone()
            return self.as_record(row), True

    def finish(self, item_id: int, decision: Decision) -> StoredMessage:
        review = "pending" if decision.label in ("lead", "needs_review") else "not_required"
        with self.connect() as db:
            db.execute(
                """UPDATE messages SET label=?,score=?,reason=?,draft=?,review_status=?
                   WHERE id=? AND label='processing'""",
                (decision.label, decision.score, decision.reason, decision.draft, review, item_id),
            )
        result = self.get(item_id)
        assert result is not None
        return result

    def get(self, item_id: int) -> StoredMessage | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM messages WHERE id=?", (item_id,)).fetchone()
        return self.as_record(row) if row is not None else None

    def list_items(self, label: str | None = None) -> list[StoredMessage]:
        with self.connect() as db:
            if label:
                rows = db.execute("SELECT * FROM messages WHERE label=? ORDER BY id DESC", (label,)).fetchall()
            else:
                rows = db.execute("SELECT * FROM messages ORDER BY id DESC").fetchall()
        return [self.as_record(row) for row in rows]

    def review(self, item_id: int, action: str) -> StoredMessage:
        review_state = "approved" if action == "approve" else "rejected"
        with self.connect() as db:
            cur = db.execute(
                """UPDATE messages SET review_status=?
                   WHERE id=? AND label IN ('lead','needs_review') AND review_status='pending'""",
                (review_state, item_id),
            )
            if cur.rowcount != 1:
                raise ValueError("Only an unreviewed lead may be reviewed")
        result = self.get(item_id)
        assert result is not None
        return result
