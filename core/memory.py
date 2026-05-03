"""
core/memory.py — Persistent Conversation Memory
SQLite-backed conversation history with recency and search support.
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("bharvishya.memory")


class ConversationMemory:
    """
    Persistent conversation memory using SQLite.

    Schema:
        conversations(id, timestamp, user_msg, assistant_msg, skill_used, metadata)
    """

    def __init__(self, db_path: str = "data/memory.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        logger.info(f"Memory initialized at {db_path}")

    def _init_schema(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT,
            timestamp TEXT NOT NULL,
            user_msg TEXT NOT NULL,
            assistant_msg TEXT NOT NULL,
            skill_used TEXT,
            metadata TEXT
        )
        """)
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_timestamp ON conversations(timestamp)"
        )
        self.conn.commit()

    def add(
        self,
        user: str,
        assistant: str,
        skill_used=None,
        metadata=None,
        conversation_id=None,  # NEW
    ):
        if not conversation_id:
            conversation_id = f"legacy_{datetime.utcnow().timestamp()}"

        cursor = self.conn.execute(
            """
            INSERT INTO conversations 
            (conversation_id, timestamp, user_msg, assistant_msg, skill_used, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                datetime.utcnow().isoformat(),
                user,
                assistant,
                skill_used,
                json.dumps(metadata) if metadata else None,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_recent(self, limit: int = 20) -> List[dict]:
        """Return the N most recent conversation turns (oldest first)."""
        rows = self.conn.execute(
            """
            SELECT timestamp, user_msg, assistant_msg, skill_used
            FROM conversations
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            {
                "timestamp": r["timestamp"],
                "user": r["user_msg"],
                "assistant": r["assistant_msg"],
                "skill_used": r["skill_used"],
            }
            for r in reversed(rows)
        ]

    def search(self, query: str, limit: int = 10) -> List[dict]:
        """Full-text search over conversation history."""
        rows = self.conn.execute(
            """
            SELECT timestamp, user_msg, assistant_msg, skill_used
            FROM conversations
            WHERE user_msg LIKE ? OR assistant_msg LIKE ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (f"%{query}%", f"%{query}%", limit),
        ).fetchall()
        return [
            {
                "timestamp": r["timestamp"],
                "user": r["user_msg"],
                "assistant": r["assistant_msg"],
                "skill_used": r["skill_used"],
            }
            for r in rows
        ]

    def stats(self) -> dict:
        """Return memory statistics."""
        row = self.conn.execute(
            "SELECT COUNT(*) as total, MIN(timestamp) as first, MAX(timestamp) as last FROM conversations"
        ).fetchone()
        return {
            "total_turns": row["total"],
            "first_conversation": row["first"],
            "last_conversation": row["last"],
        }
    
    def get_conversations(self, limit=20):
        rows = self.conn.execute("""
            SELECT c1.conversation_id,
                c1.user_msg as title,
                c2.last_time,
                c2.turns
            FROM conversations c1
            JOIN (
                SELECT conversation_id,
                    MAX(timestamp) as last_time,
                    COUNT(*) as turns
                FROM conversations
                GROUP BY conversation_id
            ) c2
            ON c1.conversation_id = c2.conversation_id
            WHERE c1.id = (
                SELECT MIN(id)
                FROM conversations
                WHERE conversation_id = c1.conversation_id
            )
            ORDER BY c2.last_time DESC
            LIMIT ?
        """, (limit,)).fetchall()

        return [
            {
                "conversation_id": r["conversation_id"],
                "title": r["title"],
                "last_time": r["last_time"],
                "turns": r["turns"]
            }
            for r in rows
        ]
    
    def get_conversation(self, cid):
        rows = self.conn.execute("""
            SELECT user_msg, assistant_msg, skill_used
            FROM conversations
            WHERE conversation_id = ?
            ORDER BY id ASC
        """, (cid,)).fetchall()

        return [
            {
                "user": r["user_msg"],
                "assistant": r["assistant_msg"],
                "skill_used": r["skill_used"]
            }
            for r in rows
        ]

    def clear_all(self):
        """Wipe all conversation history."""
        self.conn.execute("DELETE FROM conversations")
        self.conn.commit()
        logger.warning("All conversation history cleared")

    def close(self):
        self.conn.close()
