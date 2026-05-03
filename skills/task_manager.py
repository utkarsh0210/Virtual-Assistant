# """
# skills/task_manager.py — Task Manager & Notes Skill
# Persistent SQLite-backed task/note management.
# """

# import asyncio
# import asyncio
# import logging
# import sqlite3
# import uuid
# from datetime import datetime
# from pathlib import Path
# from typing import Any, Dict, List, Optional
# import asyncio
# from skills.registry import BaseSkill

# logger = logging.getLogger("bharvishya.skill.task_manager")


# class TaskDB:
#     """Lightweight SQLite task store."""

#     def __init__(self, db_path: str = "data/tasks.db"):
#         Path(db_path).parent.mkdir(parents=True, exist_ok=True)
#         self.conn = sqlite3.connect(db_path, check_same_thread=False)
#         self.conn.row_factory = sqlite3.Row
#         self._init()

#     def _init(self):
#         self.conn.execute("""
#             CREATE TABLE IF NOT EXISTS tasks (
#                 id          TEXT PRIMARY KEY,
#                 text        TEXT NOT NULL,
#                 priority    TEXT DEFAULT 'normal',
#                 completed   INTEGER DEFAULT 0,
#                 created_at  TEXT NOT NULL,
#                 completed_at TEXT,
#                 tags        TEXT
#             )
#         """)
#         self.conn.commit()


# class Skill(BaseSkill):
#     name = "task_manager"
#     description = "Create, list, complete, and manage tasks and notes"
#     actions = ["add", "list", "complete", "delete", "search", "clear_completed"]

#     def __init__(self):
#         self.db = TaskDB()

#     async def execute(self, action: str, params: Dict[str, Any]) -> Any:
#         dispatch = {
#             "add": self._add,
#             "list": self._list,
#             "complete": self._complete,
#             "delete": self._delete,
#             "search": self._search,
#             "clear_completed": self._clear_completed,
#         }
#         handler = dispatch.get(action, self._list)
#         return await asyncio.to_thread(handler, params)


#     def _add(self, params: dict) -> dict:
#         task_id = str(uuid.uuid4())[:8]
#         text = params.get("text", "").strip()
#         priority = params.get("priority", "normal")
#         tags = params.get("tags", "")

#         if not text:
#             return {"error": "Task text cannot be empty"}

#         self.db.conn.execute(
#             "INSERT INTO tasks (id, text, priority, created_at, tags) VALUES (?, ?, ?, ?, ?)",
#             (task_id, text, priority, datetime.utcnow().isoformat(), tags),
#         )
#         self.db.conn.commit()
#         logger.info(f"Task added: {task_id} — {text!r}")
#         return {"task_id": task_id, "text": text, "priority": priority, "status": "added"}

#     def _list(self, params: dict) -> dict:
#         show_completed = params.get("show_completed", False)
#         query = "SELECT * FROM tasks"
#         if not show_completed:
#             query += " WHERE completed = 0"
#         query += " ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 WHEN 'low' THEN 2 END, created_at"

#         rows = self.db.conn.execute(query).fetchall()
#         tasks = [
#             {
#                 "id": r["id"],
#                 "text": r["text"],
#                 "priority": r["priority"],
#                 "completed": bool(r["completed"]),
#                 "created_at": r["created_at"],
#                 "tags": r["tags"],
#             }
#             for r in rows
#         ]
#         return {"tasks": tasks, "count": len(tasks)}

#     def _complete(self, params: dict) -> dict:
#         task_id = params.get("task_id", "")
#         # Support partial ID match
#         rows = self.db.conn.execute(
#             "SELECT id FROM tasks WHERE id LIKE ? AND completed = 0",
#             (f"%{task_id}%",),
#         ).fetchall()

#         if not rows:
#             return {"error": f"No pending task found matching '{task_id}'"}

#         target_id = rows[0]["id"]
#         self.db.conn.execute(
#             "UPDATE tasks SET completed = 1, completed_at = ? WHERE id = ?",
#             (datetime.utcnow().isoformat(), target_id),
#         )
#         self.db.conn.commit()
#         return {"task_id": target_id, "status": "completed"}

#     def _delete(self, params: dict) -> dict:
#         task_id = params.get("task_id", "")
#         rows = self.db.conn.execute(
#             "SELECT id, text FROM tasks WHERE id LIKE ?", (f"%{task_id}%",)
#         ).fetchall()

#         if not rows:
#             return {"error": f"No task found matching '{task_id}'"}

#         target_id = rows[0]["id"]
#         self.db.conn.execute("DELETE FROM tasks WHERE id = ?", (target_id,))
#         self.db.conn.commit()
#         return {"task_id": target_id, "status": "deleted"}

#     def _search(self, params: dict) -> dict:
#         query = params.get("query", "")
#         rows = self.db.conn.execute(
#             "SELECT * FROM tasks WHERE text LIKE ? ORDER BY created_at DESC",
#             (f"%{query}%",),
#         ).fetchall()
#         tasks = [
#             {"id": r["id"], "text": r["text"], "priority": r["priority"], "completed": bool(r["completed"])}
#             for r in rows
#         ]
#         return {"tasks": tasks, "count": len(tasks)}

#     def _clear_completed(self, params: dict) -> dict:
#         cursor = self.db.conn.execute("DELETE FROM tasks WHERE completed = 1")
#         self.db.conn.commit()
#         return {"deleted_count": cursor.rowcount, "status": "cleared"}

#     # ── Public helpers (used by REST API) ─────────────────────────────────────
#     def list_tasks(self) -> List[dict]:
#         return self._list({})["tasks"]

#     def add_task(self, text: str, priority: str = "normal") -> dict:
#         return self._add({"text": text, "priority": priority})

#     def delete_task(self, task_id: str):
#         self._delete({"task_id": task_id})

#     def complete_task(self, task_id: str):
#         self._complete({"task_id": task_id})



"""
skills/task_manager.py — Task Manager & Notes Skill
Persistent SQLite-backed task/note management.
"""

import asyncio
import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from skills.registry import BaseSkill

logger = logging.getLogger("bharvishya.skill.task_manager")


class TaskDB:
    """Lightweight SQLite task store."""

    def __init__(self, db_path: str = "data/tasks.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id          TEXT PRIMARY KEY,
                text        TEXT NOT NULL,
                priority    TEXT DEFAULT 'normal',
                completed   INTEGER DEFAULT 0,
                created_at  TEXT NOT NULL,
                completed_at TEXT,
                tags        TEXT
            )
        """)
        self.conn.commit()


class Skill(BaseSkill):
    name = "task_manager"
    description = "Create, list, complete, and manage tasks and notes"
    actions = ["add", "list", "complete", "delete", "search", "clear_completed"]

    def __init__(self):
        self.db = TaskDB()

    async def execute(self, action: str, params: Dict[str, Any]) -> Any:
        # FIX: All handlers perform synchronous SQLite I/O which blocks the event
        # loop. Wrap dispatch in asyncio.to_thread() — same pattern used correctly
        # in calendar_skill.py.
        dispatch = {
            "add": self._add,
            "list": self._list,
            "complete": self._complete,
            "delete": self._delete,
            "search": self._search,
            "clear_completed": self._clear_completed,
        }
        handler = dispatch.get(action, self._list)
        return await asyncio.to_thread(handler, params)

    def _add(self, params: dict) -> dict:
        task_id = str(uuid.uuid4())[:8]
        text = params.get("text", "").strip()
        priority = params.get("priority", "normal")
        tags = params.get("tags", "")

        if not text:
            return {"error": "Task text cannot be empty"}

        self.db.conn.execute(
            "INSERT INTO tasks (id, text, priority, created_at, tags) VALUES (?, ?, ?, ?, ?)",
            (task_id, text, priority, datetime.utcnow().isoformat(), tags),
        )
        self.db.conn.commit()
        logger.info(f"Task added: {task_id} — {text!r}")
        return {"task_id": task_id, "text": text, "priority": priority, "status": "added"}

    def _list(self, params: dict) -> dict:
        show_completed = params.get("show_completed", False)
        query = "SELECT * FROM tasks"
        if not show_completed:
            query += " WHERE completed = 0"
        query += (
            " ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 WHEN 'low' THEN 2 END,"
            " created_at"
        )

        rows = self.db.conn.execute(query).fetchall()
        tasks = [
            {
                "id": r["id"],
                "text": r["text"],
                "priority": r["priority"],
                "completed": bool(r["completed"]),
                "created_at": r["created_at"],
                "tags": r["tags"],
            }
            for r in rows
        ]
        return {"tasks": tasks, "count": len(tasks)}

    def _complete(self, params: dict) -> dict:
        task_id = params.get("task_id", "")
        rows = self.db.conn.execute(
            "SELECT id FROM tasks WHERE id LIKE ? AND completed = 0",
            (f"%{task_id}%",),
        ).fetchall()

        if not rows:
            return {"error": f"No pending task found matching '{task_id}'"}

        target_id = rows[0]["id"]
        self.db.conn.execute(
            "UPDATE tasks SET completed = 1, completed_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), target_id),
        )
        self.db.conn.commit()
        return {"task_id": target_id, "status": "completed"}

    def _delete(self, params: dict) -> dict:
        task_id = params.get("task_id", "")
        rows = self.db.conn.execute(
            "SELECT id, text FROM tasks WHERE id LIKE ?", (f"%{task_id}%",)
        ).fetchall()

        if not rows:
            return {"error": f"No task found matching '{task_id}'"}

        target_id = rows[0]["id"]
        self.db.conn.execute("DELETE FROM tasks WHERE id = ?", (target_id,))
        self.db.conn.commit()
        return {"task_id": target_id, "status": "deleted"}

    def _search(self, params: dict) -> dict:
        query = params.get("query", "")
        rows = self.db.conn.execute(
            "SELECT * FROM tasks WHERE text LIKE ? ORDER BY created_at DESC",
            (f"%{query}%",),
        ).fetchall()
        tasks = [
            {
                "id": r["id"],
                "text": r["text"],
                "priority": r["priority"],
                "completed": bool(r["completed"]),
            }
            for r in rows
        ]
        return {"tasks": tasks, "count": len(tasks)}

    def _clear_completed(self, params: dict) -> dict:
        cursor = self.db.conn.execute("DELETE FROM tasks WHERE completed = 1")
        self.db.conn.commit()
        return {"deleted_count": cursor.rowcount, "status": "cleared"}

    # ── Public helpers (used by REST API) ─────────────────────────────────────
    def list_tasks(self) -> List[dict]:
        return self._list({})["tasks"]

    def add_task(self, text: str, priority: str = "normal") -> dict:
        return self._add({"text": text, "priority": priority})

    def delete_task(self, task_id: str):
        self._delete({"task_id": task_id})

    def complete_task(self, task_id: str):
        self._complete({"task_id": task_id})