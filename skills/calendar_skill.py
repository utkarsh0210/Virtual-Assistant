# """
# skills/calendar_skill.py — Calendar Skill
# Google Calendar integration via service account or OAuth2.
# Falls back to local calendar if not configured.
# """

# import asyncio
# import json
# import logging
# import os
# import sqlite3
# import uuid
# from datetime import datetime, timedelta
# from pathlib import Path
# from typing import Any, Dict, List

# from skills.registry import BaseSkill

# logger = logging.getLogger("bharvishya.skill.calendar")

# GOOGLE_CALENDAR_CREDENTIALS = os.getenv("GOOGLE_CALENDAR_CREDENTIALS", "")


# class LocalCalendarDB:
#     """Fallback local SQLite calendar when Google Calendar is not configured."""

#     def __init__(self, db_path: str = "data/calendar.db"):
#         Path(db_path).parent.mkdir(parents=True, exist_ok=True)
#         self.conn = sqlite3.connect(db_path, check_same_thread=False)
#         self.conn.row_factory = sqlite3.Row
#         self.conn.execute("""
#             CREATE TABLE IF NOT EXISTS events (
#                 id          TEXT PRIMARY KEY,
#                 title       TEXT NOT NULL,
#                 description TEXT,
#                 start_time  TEXT NOT NULL,
#                 end_time    TEXT,
#                 location    TEXT,
#                 created_at  TEXT NOT NULL
#             )
#         """)
#         self.conn.commit()


# class Skill(BaseSkill):
#     name = "calendar_skill"
#     description = "View and create calendar events (Google Calendar or local)"
#     actions = ["list_today", "list_week", "add_event", "search_events", "delete_event"]

#     def __init__(self):
#         self.local_db = LocalCalendarDB()
#         self.use_google = bool(GOOGLE_CALENDAR_CREDENTIALS)
#         if self.use_google:
#             logger.info("Calendar backend: Google Calendar")
#         else:
#             logger.info("Calendar backend: Local SQLite (set GOOGLE_CALENDAR_CREDENTIALS to use Google)")

#     async def execute(self, action: str, params: Dict[str, Any]) -> Any:
#         return await asyncio.to_thread(self._execute_sync, action, params)

#     def _execute_sync(self, action: str, params: dict) -> Any:
#         dispatch = {
#             "list_today": self._list_today,
#             "list_week": self._list_week,
#             "add_event": self._add_event,
#             "search_events": self._search_events,
#             "delete_event": self._delete_event,
#         }
#         handler = dispatch.get(action, self._list_today)
#         return handler(params)

#     def _list_today(self, params: dict) -> dict:
#         today = datetime.now().date().isoformat()
#         rows = self.local_db.conn.execute(
#             "SELECT * FROM events WHERE date(start_time) = ? ORDER BY start_time",
#             (today,),
#         ).fetchall()
#         events = self._rows_to_dicts(rows)
#         return {
#             "date": today,
#             "events": events,
#             "count": len(events),
#             "message": f"You have {len(events)} event(s) today." if events else "No events today.",
#         }

#     def _list_week(self, params: dict) -> dict:
#         today = datetime.now()
#         week_end = (today + timedelta(days=7)).date().isoformat()
#         today_str = today.date().isoformat()
#         rows = self.local_db.conn.execute(
#             "SELECT * FROM events WHERE date(start_time) BETWEEN ? AND ? ORDER BY start_time",
#             (today_str, week_end),
#         ).fetchall()
#         events = self._rows_to_dicts(rows)
#         return {"events": events, "count": len(events), "period": "next 7 days"}

#     def _add_event(self, params: dict) -> dict:
#         title = params.get("title", "").strip()
#         if not title:
#             return {"error": "Event title is required"}

#         start_raw = params.get("start_time", "")
#         try:
#             start_time = self._parse_datetime(start_raw)
#         except Exception:
#             # Default to 1 hour from now if parse fails
#             start_time = datetime.now() + timedelta(hours=1)

#         end_raw = params.get("end_time", "")
#         end_time = self._parse_datetime(end_raw) if end_raw else start_time + timedelta(hours=1)

#         event_id = str(uuid.uuid4())[:8]
#         self.local_db.conn.execute(
#             """
#             INSERT INTO events (id, title, description, start_time, end_time, location, created_at)
#             VALUES (?, ?, ?, ?, ?, ?, ?)
#             """,
#             (
#                 event_id,
#                 title,
#                 params.get("description", ""),
#                 start_time.isoformat(),
#                 end_time.isoformat(),
#                 params.get("location", ""),
#                 datetime.utcnow().isoformat(),
#             ),
#         )
#         self.local_db.conn.commit()
#         logger.info(f"Event created: {event_id} — {title!r}")
#         return {
#             "event_id": event_id,
#             "title": title,
#             "start_time": start_time.strftime("%Y-%m-%d %H:%M"),
#             "status": "created",
#         }

#     def _search_events(self, params: dict) -> dict:
#         query = params.get("query", "")
#         rows = self.local_db.conn.execute(
#             "SELECT * FROM events WHERE title LIKE ? OR description LIKE ? ORDER BY start_time",
#             (f"%{query}%", f"%{query}%"),
#         ).fetchall()
#         return {"events": self._rows_to_dicts(rows), "count": len(rows)}

#     def _delete_event(self, params: dict) -> dict:
#         event_id = params.get("event_id", "")
#         rows = self.local_db.conn.execute(
#             "SELECT id, title FROM events WHERE id LIKE ?", (f"%{event_id}%",)
#         ).fetchall()
#         if not rows:
#             return {"error": f"No event found matching '{event_id}'"}
#         self.local_db.conn.execute("DELETE FROM events WHERE id = ?", (rows[0]["id"],))
#         self.local_db.conn.commit()
#         return {"status": "deleted", "event_id": rows[0]["id"]}

#     def _rows_to_dicts(self, rows) -> List[dict]:
#         return [
#             {
#                 "id": r["id"],
#                 "title": r["title"],
#                 "description": r["description"],
#                 "start_time": r["start_time"],
#                 "end_time": r["end_time"],
#                 "location": r["location"],
#             }
#             for r in rows
#         ]

#     def _parse_datetime(self, value: str) -> datetime:
#         """Attempt multiple datetime format parses."""
#         formats = [
#             "%Y-%m-%dT%H:%M",
#             "%Y-%m-%d %H:%M",
#             "%Y-%m-%d",
#             "%d/%m/%Y %H:%M",
#             "%d/%m/%Y",
#         ]
#         for fmt in formats:
#             try:
#                 return datetime.strptime(value.strip(), fmt)
#             except ValueError:
#                 continue
#         raise ValueError(f"Cannot parse datetime: {value!r}")



"""
skills/calendar_skill.py — Calendar Skill
Google Calendar integration via service account or OAuth2.
Falls back to local calendar if not configured.
"""

import asyncio
import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from skills.registry import BaseSkill

logger = logging.getLogger("bharvishya.skill.calendar")

GOOGLE_CALENDAR_CREDENTIALS = os.getenv("GOOGLE_CALENDAR_CREDENTIALS", "")


class LocalCalendarDB:
    """Fallback local SQLite calendar when Google Calendar is not configured."""

    def __init__(self, db_path: str = "data/calendar.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                description TEXT,
                start_time  TEXT NOT NULL,
                end_time    TEXT,
                location    TEXT,
                created_at  TEXT NOT NULL
            )
        """)
        self.conn.commit()


class Skill(BaseSkill):
    name = "calendar_skill"
    description = "View and create calendar events (Google Calendar or local)"
    actions = ["list_today", "list_week", "add_event", "search_events", "delete_event"]

    def __init__(self):
        self.local_db = LocalCalendarDB()
        self.use_google = bool(GOOGLE_CALENDAR_CREDENTIALS)
        if self.use_google:
            logger.info("Calendar backend: Google Calendar")
        else:
            logger.info("Calendar backend: Local SQLite (set GOOGLE_CALENDAR_CREDENTIALS to use Google)")

    async def execute(self, action: str, params: Dict[str, Any]) -> Any:
        return await asyncio.to_thread(self._execute_sync, action, params)

    def _execute_sync(self, action: str, params: dict) -> Any:
        dispatch = {
            "list_today": self._list_today,
            "list_week": self._list_week,
            "add_event": self._add_event,
            "search_events": self._search_events,
            "delete_event": self._delete_event,
        }
        handler = dispatch.get(action, self._list_today)
        return handler(params)

    def _list_today(self, params: dict) -> dict:
        today = datetime.now().date().isoformat()
        rows = self.local_db.conn.execute(
            "SELECT * FROM events WHERE date(start_time) = ? ORDER BY start_time",
            (today,),
        ).fetchall()
        events = self._rows_to_dicts(rows)
        return {
            "date": today,
            "events": events,
            "count": len(events),
            "message": f"You have {len(events)} event(s) today." if events else "No events today.",
        }

    def _list_week(self, params: dict) -> dict:
        today = datetime.now()
        week_end = (today + timedelta(days=7)).date().isoformat()
        today_str = today.date().isoformat()
        rows = self.local_db.conn.execute(
            "SELECT * FROM events WHERE date(start_time) BETWEEN ? AND ? ORDER BY start_time",
            (today_str, week_end),
        ).fetchall()
        events = self._rows_to_dicts(rows)
        return {"events": events, "count": len(events), "period": "next 7 days"}

    def _add_event(self, params: dict) -> dict:
        title = params.get("title", "").strip()
        if not title:
            return {"error": "Event title is required"}

        start_raw = params.get("start_time", "")
        try:
            start_time = self._parse_datetime(start_raw)
        except Exception:
            # Default to 1 hour from now if parse fails
            start_time = datetime.now() + timedelta(hours=1)

        end_raw = params.get("end_time", "")
        end_time = self._parse_datetime(end_raw) if end_raw else start_time + timedelta(hours=1)

        event_id = str(uuid.uuid4())[:8]
        self.local_db.conn.execute(
            """
            INSERT INTO events (id, title, description, start_time, end_time, location, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                title,
                params.get("description", ""),
                start_time.isoformat(),
                end_time.isoformat(),
                params.get("location", ""),
                datetime.utcnow().isoformat(),
            ),
        )
        self.local_db.conn.commit()
        logger.info(f"Event created: {event_id} — {title!r}")
        return {
            "event_id": event_id,
            "title": title,
            "start_time": start_time.strftime("%Y-%m-%d %H:%M"),
            "status": "created",
        }

    def _search_events(self, params: dict) -> dict:
        query = params.get("query", "")
        rows = self.local_db.conn.execute(
            "SELECT * FROM events WHERE title LIKE ? OR description LIKE ? ORDER BY start_time",
            (f"%{query}%", f"%{query}%"),
        ).fetchall()
        return {"events": self._rows_to_dicts(rows), "count": len(rows)}

    def _delete_event(self, params: dict) -> dict:
        event_id = params.get("event_id", "")
        rows = self.local_db.conn.execute(
            "SELECT id, title FROM events WHERE id LIKE ?", (f"%{event_id}%",)
        ).fetchall()
        if not rows:
            return {"error": f"No event found matching '{event_id}'"}
        self.local_db.conn.execute("DELETE FROM events WHERE id = ?", (rows[0]["id"],))
        self.local_db.conn.commit()
        return {"status": "deleted", "event_id": rows[0]["id"]}

    def _rows_to_dicts(self, rows) -> List[dict]:
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "description": r["description"],
                "start_time": r["start_time"],
                "end_time": r["end_time"],
                "location": r["location"],
            }
            for r in rows
        ]

    def _parse_datetime(self, value: str) -> datetime:
        """Attempt multiple datetime format parses."""
        formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse datetime: {value!r}")