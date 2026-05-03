# """
# skills/email_skill.py — Email Agent
# A full email agent that can:
#   - send        : Compose and send an email
#   - read_inbox  : Fetch recent emails from Gmail inbox
#   - search      : Search inbox by keyword/topic + optional date filter
#   - summarize   : AI-powered summary of fetched emails (Gemini)
#   - reply       : Reply to a specific email by UID
#   - delete      : Move an email to Trash by UID
#   - mark_read   : Mark an email as read by UID
#   - check_config: Verify credentials are configured

# Uses IMAP SSL (read) + SMTP SSL (send). Works with Gmail App Passwords.
# Requires: EMAIL_ADDRESS and EMAIL_APP_PASSWORD in .env
# """

# import asyncio
# import email
# import imaplib
# import logging
# import os
# import smtplib
# import ssl
# from datetime import datetime, timedelta
# from email.header import decode_header
# from email.message import EmailMessage
# from typing import Any, Dict, List, Optional
# import asyncio

# import google.generativeai as genai

# from skills.registry import BaseSkill

# logger = logging.getLogger("bharvishya.skill.email")

# # ── Config from .env ──────────────────────────────────────────────────────────
# SMTP_HOST  = os.getenv("EMAIL_SMTP_HOST",   "smtp.gmail.com")
# SMTP_PORT  = int(os.getenv("EMAIL_SMTP_PORT", "465"))
# IMAP_HOST  = os.getenv("EMAIL_IMAP_HOST",   "imap.gmail.com")
# IMAP_PORT  = int(os.getenv("EMAIL_IMAP_PORT", "993"))
# EMAIL_ADDR = os.getenv("EMAIL_ADDRESS",      "")
# EMAIL_PASS = os.getenv("EMAIL_APP_PASSWORD", "")


# # ── MIME / parsing helpers ────────────────────────────────────────────────────

# def _decode_header_value(s: str) -> str:
#     """Decode RFC2047 encoded header words like =?UTF-8?b?...?="""
#     if not s:
#         return ""
#     parts = decode_header(s)
#     out = []
#     for part, enc in parts:
#         if isinstance(part, bytes):
#             out.append(part.decode(enc or "utf-8", errors="replace"))
#         else:
#             out.append(str(part))
#     return " ".join(out)


# def _strip_html(html: str) -> str:
#     """
#     Strip HTML tags and decode entities to get readable plain text.
#     No external library needed — uses stdlib html.parser.
#     """
#     import html as html_lib
#     from html.parser import HTMLParser

#     class _Stripper(HTMLParser):
#         def __init__(self):
#             super().__init__()
#             self.parts = []
#             self._skip = False

#         def handle_starttag(self, tag, attrs):
#             if tag in ("script", "style", "head"):
#                 self._skip = True
#             if tag in ("br", "p", "div", "tr", "li"):
#                 self.parts.append("\n")

#         def handle_endtag(self, tag):
#             if tag in ("script", "style", "head"):
#                 self._skip = False

#         def handle_data(self, data):
#             if not self._skip:
#                 self.parts.append(data)

#     stripper = _Stripper()
#     try:
#         stripper.feed(html)
#     except Exception:
#         pass

#     text = "".join(stripper.parts)
#     text = html_lib.unescape(text)
#     # Collapse excessive whitespace / blank lines
#     import re
#     text = re.sub(r"\n{3,}", "\n\n", text)
#     text = re.sub(r"[ \t]+", " ", text)
#     return text.strip()


# def _extract_body(msg: email.message.Message) -> str:
#     """
#     Extract readable plain text from a possibly multipart email.
#     Prefers text/plain. Falls back to text/html → strip tags.
#     This is critical: many modern emails are HTML-only, so without
#     stripping we'd be searching raw CSS/HTML tags, missing the actual content.
#     """
#     plain = ""
#     html  = ""

#     if msg.is_multipart():
#         for part in msg.walk():
#             ct = part.get_content_type()
#             cd = str(part.get("Content-Disposition", ""))
#             if "attachment" in cd:
#                 continue
#             payload = part.get_payload(decode=True)
#             if not payload:
#                 continue
#             charset = part.get_content_charset() or "utf-8"
#             decoded = payload.decode(charset, errors="replace")
#             if ct == "text/plain" and not plain:
#                 plain = decoded
#             elif ct == "text/html" and not html:
#                 html = decoded
#     else:
#         payload = msg.get_payload(decode=True)
#         if payload:
#             charset = msg.get_content_charset() or "utf-8"
#             decoded = payload.decode(charset, errors="replace")
#             ct = msg.get_content_type()
#             if ct == "text/html":
#                 html = decoded
#             else:
#                 plain = decoded

#     if plain.strip():
#         return plain.strip()
#     if html.strip():
#         return _strip_html(html)
#     return ""


# def _parse_date(date_str: str) -> Optional[datetime]:
#     try:
#         from email.utils import parsedate_to_datetime
#         return parsedate_to_datetime(date_str)
#     except Exception:
#         return None


# def _connect_imap() -> imaplib.IMAP4_SSL:
#     mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
#     mail.login(EMAIL_ADDR, EMAIL_PASS)
#     return mail


# # ── Gemini summarization ──────────────────────────────────────────────────────

# def _ai_summarize(emails: List[dict], topic: str) -> str:
#     """
#     Call Gemini to produce a rich structured markdown summary of emails.
#     Each email gets: summary, category, action-needed.
#     Ends with an overall insight block.
#     """
#     api_key = os.getenv("GEMINI_API_KEY", "")
#     if not api_key or not emails:
#         return ""

#     genai.configure(api_key=api_key)
#     model = genai.GenerativeModel(
#         model_name=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview"),
#         generation_config=genai.GenerationConfig(temperature=0.3, max_output_tokens=1500),
#     )

#     digest = ""
#     for i, em in enumerate(emails, 1):
#         digest += (
#             f"\n--- EMAIL {i} ---\n"
#             f"From: {em['from']}\n"
#             f"Subject: {em['subject']}\n"
#             f"Date: {em['date']}\n"
#             f"Body snippet: {em['body'][:500]}\n"
#         )

#     prompt = (
#         f"You are an email intelligence assistant. "
#         f"The user asked about emails related to: '{topic}'.\n"
#         f"Here are the emails:\n{digest}\n\n"
#         "For EACH email, write a summary block in this exact format:\n\n"
#         "**[N]. <Subject>** — <Sender> · <Date>\n"
#         "📌 **Summary:** 2-3 sentence summary of what this email is about.\n"
#         "🏷️ **Category:** (Job Opportunity / Interview Invite / Rejection / "
#         "Follow-up / Offer Letter / Newsletter / Other)\n"
#         "⚡ **Action Required:** Yes or No — if Yes, state what action.\n"
#         "---\n\n"
#         "After all emails add:\n"
#         "### 📊 Overall Insight\n"
#         "2-3 sentences summarising patterns, urgency, and your recommendation.\n\n"
#         "Be concise. No preamble. Start directly with EMAIL 1."
#     )

#     try:
#         return model.generate_content(prompt).text.strip()
#     except Exception as e:
#         logger.error(f"Gemini summarization error: {e}")
#         return ""


# # ── Skill ─────────────────────────────────────────────────────────────────────

# class Skill(BaseSkill):
#     name = "email_skill"
#     description = (
#         "Full email agent: send emails, read inbox, search by topic/date, "
#         "AI-summarize results, reply to emails, delete, mark as read."
#     )
#     actions = [
#     "send", "read_inbox", "search", "summarize",
#     "reply", "delete", "mark_read", "check_config",
#     ]

#     def __init__(self):
#         self._last_result: dict = {}

#     # ── Router ─────────────────────────────────────────────────────────────────
#     async def execute(self, action: str, params: Dict[str, Any]) -> Any:
#         if action == "check_config":
#             return self._check_config()

#         if not EMAIL_ADDR or not EMAIL_PASS:
#             return {
#                 "error": "Email not configured.",
#                 "help":  "Set EMAIL_ADDRESS and EMAIL_APP_PASSWORD in your .env file.",
#             }

#         handlers = {
#             "send":       self._send,
#             "read_inbox": self._read_inbox,
#             "search":     self._search,
#             "summarize":  self._summarize,
#             "reply":      self._reply,
#             "delete":     self._delete,
#             "mark_read":  self._mark_read,
#         }
#         handler = handlers.get(action)
#         if not handler:
#             return {"error": f"Unknown action: {action}"}

#         # All IMAP/SMTP calls are blocking — run off the event loop
#         result = await asyncio.to_thread(handler, params)

#         # Cache so WebSocket handler can send rich email_results message
#         self._last_result = result if isinstance(result, dict) else {}
#         return result

#     # ── check_config ───────────────────────────────────────────────────────────
#     def _check_config(self) -> dict:
#         ok = bool(EMAIL_ADDR and EMAIL_PASS)
#         return {
#             "configured":   ok,
#             "email_address": EMAIL_ADDR if ok else None,
#             "smtp_host":    SMTP_HOST,
#             "imap_host":    IMAP_HOST,
#             "message": (
#                 f"Email agent ready. Connected as {EMAIL_ADDR}."
#                 if ok else
#                 "Set EMAIL_ADDRESS and EMAIL_APP_PASSWORD in your .env file."
#             ),
#         }

#     # ── send ───────────────────────────────────────────────────────────────────
#     def _send(self, params: dict) -> dict:
#         to      = params.get("to", "").strip()
#         subject = params.get("subject", "Message from Bharvishya").strip()
#         body    = params.get("body", "").strip()
#         cc      = params.get("cc", "")

#         if not to:
#             return {"error": "Recipient email address is required."}
#         if not body:
#             return {"error": "Email body cannot be empty."}

#         em = EmailMessage()
#         em["From"]    = EMAIL_ADDR
#         em["To"]      = to
#         em["Subject"] = subject
#         if cc:
#             em["Cc"] = cc
#         em.set_content(body)

#         ctx = ssl.create_default_context()
#         try:
#             with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as smtp:
#                 smtp.login(EMAIL_ADDR, EMAIL_PASS)
#                 smtp.send_message(em)
#             logger.info(f"Email sent → {to}: {subject!r}")
#             return {
#                 "status":  "sent",
#                 "to":      to,
#                 "subject": subject,
#                 "message": f"Email successfully sent to {to}.",
#             }
#         except smtplib.SMTPAuthenticationError:
#             return {"error": "SMTP auth failed. Check your Gmail App Password."}
#         except smtplib.SMTPRecipientsRefused:
#             return {"error": f"Recipient {to!r} was refused by the server."}
#         except Exception as e:
#             logger.error(f"Send error: {e}")
#             return {"error": "Failed to send. Please try again."}

#     # ── read_inbox ─────────────────────────────────────────────────────────────
#     def _read_inbox(self, params: dict) -> dict:
#         """
#         Fetch recent emails from inbox.
#         params: limit (int), days (int), unread (bool)
#         """
#         limit       = int(params.get("limit", 10))
#         days        = int(params.get("days", 7))
#         unread_only = bool(params.get("unread", False))

#         try:
#             mail = _connect_imap()
#             mail.select("INBOX")

#             since = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
#             crit  = f'(UNSEEN SINCE "{since}")' if unread_only else f'(SINCE "{since}")'
#             _, uids = mail.uid("search", None, crit)

#             all_uids = uids[0].split()
#             total_unread = len(all_uids)

#             uid_list = all_uids[::-1][:limit]

#             emails = [e for uid in uid_list if (e := self._fetch_one(mail, uid))]
#             mail.logout()

#             return {
#                 "status": "success",
#                 "emails": emails,
#                 "count": len(emails),
#                 "total": total_unread,   # ✅ FIX
#                 "period": f"last {days} days",
#             }
#         except imaplib.IMAP4.error as e:
#             logger.error(f"IMAP read_inbox error: {e}")
#             return {"error": f"Cannot connect to Gmail IMAP. Check credentials. ({e})"}
#         except Exception as e:
#             logger.error(f"read_inbox error: {e}")
#             return {"error": str(e)}

#     # ── search ─────────────────────────────────────────────────────────────────
#     def _search(self, params: dict) -> dict:
#         """
#         Search inbox by keyword across subject, sender, and body within a date window.
#         Strategy:
#           1. IMAP SUBJECT search (fast, server-side)
#           2. IMAP FROM search (fast, server-side)
#           3. Fetch all emails in the date window and do client-side body scan
#              (necessary because Gmail IMAP BODY search is unreliable)
#         All results are deduplicated and sorted newest-first.

#         params: query (str), days (int, default 30), limit (int, default 20), folder (str)
#         """
#         query  = params.get("query", "").strip()
#         days   = int(params.get("days", 30))
#         limit  = int(params.get("limit", 20))
#         folder = params.get("folder", "INBOX")

#         if not query:
#             return {"error": "A search query is required."}

#         query_lower = query.lower()

#         try:
#             mail = _connect_imap()
#             mail.select(folder)
#             since = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")

#             matched_uids = set()

#             # ── Pass 1: IMAP server-side SUBJECT search (fast) ────────────────
#             try:
#                 _, subj_uids = mail.uid("search", None,
#                     f'(SINCE "{since}" SUBJECT "{query}")')
#                 if subj_uids[0]:
#                     matched_uids.update(subj_uids[0].split())
#             except Exception:
#                 pass

#             # ── Pass 2: IMAP server-side FROM search (fast) ───────────────────
#             try:
#                 _, from_uids = mail.uid("search", None,
#                     f'(SINCE "{since}" FROM "{query}")')
#                 if from_uids[0]:
#                     matched_uids.update(from_uids[0].split())
#             except Exception:
#                 pass

#             # ── Pass 3: client-side body scan ─────────────────────────────────
#             # Fetch ALL email UIDs in the window, then scan body text locally.
#             # This is reliable because we strip HTML and search clean text.
#             # We cap at 100 UIDs to avoid very long scans.
#             _, all_uids_raw = mail.uid("search", None, f'(SINCE "{since}")')
#             all_uids = all_uids_raw[0].split()[::-1]  # newest first
#             scan_uids = [u for u in all_uids if u not in matched_uids][:100]

#             for uid in scan_uids:
#                 e = self._fetch_one(mail, uid)
#                 if not e:
#                     continue
#                 # Search in clean body text + subject + sender
#                 searchable = (
#                     e["subject"] + " " +
#                     e["from"]    + " " +
#                     e["from_addr"] + " " +
#                     e["body"]       # body is already HTML-stripped by _fetch_one
#                 ).lower()
#                 if query_lower in searchable:
#                     matched_uids.add(uid)

#             mail.logout()

#             # ── Fetch full data for all matched UIDs ──────────────────────────
#             if not matched_uids:
#                 return {
#                     "status": "no_results",
#                     "query":  query,
#                     "emails": [],
#                     "count":  0,
#                     "period": f"last {days} days",
#                     "message": f"No emails found matching '{query}' in the last {days} days.",
#                 }

#             mail2 = _connect_imap()
#             mail2.select(folder)
#             emails = []
#             for uid in list(matched_uids):
#                 e = self._fetch_one(mail2, uid)
#                 if e:
#                     emails.append(e)
#             mail2.logout()

#             # Sort newest first, cap at limit
#             emails.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
#             emails = emails[:limit]

#             return {
#                 "status": "success",
#                 "query":  query,
#                 "emails": emails,
#                 "count":  len(emails),
#                 "period": f"last {days} days",
#             }

#         except imaplib.IMAP4.error as e:
#             logger.error(f"IMAP search error: {e}")
#             return {"error": f"IMAP connection failed: {e}"}
#         except Exception as e:
#             logger.error(f"_search unexpected error: {e}")
#             return {"error": f"Search failed: {e}"}

#     # ── summarize ──────────────────────────────────────────────────────────────
#     def _summarize(self, params: dict) -> dict:
#         """
#         Search emails by topic + date range, then produce an AI summary.
#         params: query (str), days (int, default 5), limit (int, default 10)

#         This is the key agentic action:
#           1. Search inbox for matching emails
#           2. Pass them to Gemini for structured summarization
#           3. Return both raw email list (for UI cards) + markdown summary
#         """
#         query = params.get("query", "").strip()
#         days  = int(params.get("days", 30))   # default 30 — was 5, too narrow
#         limit = int(params.get("limit", 10))

#         if not query:
#             return {"error": "Please provide a topic to search for."}

#         # Step 1 — search
#         result = self._search({"query": query, "days": days, "limit": limit})
#         if "error" in result:
#             return result

#         emails = result.get("emails", [])
#         if not emails:
#             return {
#                 "status":  "no_results",
#                 "query":   query,
#                 "count":   0,
#                 "message": f"No emails found about '{query}' in the last {days} days.",
#                 "emails":  [],
#                 "summary": "",
#             }

#         # Step 2 — AI summarize
#         summary = _ai_summarize(emails, query)

#         return {
#             "status":  "success",
#             "query":   query,
#             "count":   len(emails),
#             "period":  f"last {days} days",
#             "emails":  emails,    # raw list — UI renders as cards
#             "summary": summary,   # markdown — UI renders as rich text
#         }

#     # ── reply ──────────────────────────────────────────────────────────────────
#     def _reply(self, params: dict) -> dict:
#         """
#         Reply to an email identified by its UID.
#         params: uid (str), body (str)
#         """
#         uid  = str(params.get("uid", "")).strip()
#         body = params.get("body", "").strip()

#         if not uid:
#             return {"error": "Email UID is required to reply."}
#         if not body:
#             return {"error": "Reply body cannot be empty."}

#         try:
#             mail = _connect_imap()
#             mail.select("INBOX")
#             original = self._fetch_one(mail, uid.encode())
#             mail.logout()
#         except Exception as e:
#             return {"error": f"Could not fetch original email: {e}"}

#         if not original:
#             return {"error": f"Email UID {uid} not found."}

#         em = EmailMessage()
#         em["From"]        = EMAIL_ADDR
#         em["To"]          = original["from_addr"]
#         em["Subject"]     = f"Re: {original['subject']}"
#         em["In-Reply-To"] = original.get("message_id", "")
#         em["References"]  = original.get("message_id", "")

#         quoted   = "\n".join(f"> {l}" for l in original["body"].splitlines())
#         em.set_content(f"{body}\n\n--- Original Message ---\n{quoted}")

#         ctx = ssl.create_default_context()
#         try:
#             with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as smtp:
#                 smtp.login(EMAIL_ADDR, EMAIL_PASS)
#                 smtp.send_message(em)
#             logger.info(f"Reply sent → {original['from_addr']}")
#             return {
#                 "status":  "sent",
#                 "to":      original["from_addr"],
#                 "subject": em["Subject"],
#                 "message": f"Reply sent to {original['from_addr']}.",
#             }
#         except Exception as e:
#             logger.error(f"Reply error: {e}")
#             return {"error": f"Failed to send reply: {e}"}

#     # ── delete ─────────────────────────────────────────────────────────────────
#     def _delete(self, params: dict) -> dict:
#         """Move email to Gmail Trash. params: uid (str)"""
#         uid = str(params.get("uid", "")).strip()
#         if not uid:
#             return {"error": "Email UID is required to delete."}
#         try:
#             mail = _connect_imap()
#             mail.select("INBOX")
#             mail.uid("COPY",  uid.encode(), "[Gmail]/Trash")
#             mail.uid("STORE", uid.encode(), "+FLAGS", "\\Deleted")
#             mail.expunge()
#             mail.logout()
#             logger.info(f"Email UID {uid} moved to Trash")
#             return {"status": "deleted", "uid": uid, "message": "Email moved to Trash."}
#         except Exception as e:
#             logger.error(f"Delete error: {e}")
#             return {"error": f"Failed to delete email: {e}"}

#     # ── mark_read ──────────────────────────────────────────────────────────────
#     def _mark_read(self, params: dict) -> dict:
#         """Mark email as read. params: uid (str)"""
#         uid = str(params.get("uid", "")).strip()
#         if not uid:
#             return {"error": "Email UID is required."}
#         try:
#             mail = _connect_imap()
#             mail.select("INBOX")
#             mail.uid("STORE", uid.encode(), "+FLAGS", "\\Seen")
#             mail.logout()
#             return {"status": "marked_read", "uid": uid, "message": "Email marked as read."}
#         except Exception as e:
#             logger.error(f"mark_read error: {e}")
#             return {"error": f"Failed to mark email as read: {e}"}

#     # ── Internal: fetch & parse one email by UID ───────────────────────────────
#     def _fetch_one(self, mail: imaplib.IMAP4_SSL, uid) -> Optional[dict]:
#         """Fetch a single email by UID bytes and return a clean dict."""
#         try:
#             _, data = mail.uid("fetch", uid if isinstance(uid, bytes) else uid.encode(), "(RFC822 FLAGS)")
#             if not data or not data[0]:
#                 return None

#             raw_bytes = data[0][1]
#             flags_raw = data[0][0].decode() if data[0][0] else ""
#             msg       = email.message_from_bytes(raw_bytes)

#             subject    = _decode_header_value(msg.get("Subject", "(No Subject)"))
#             from_raw   = _decode_header_value(msg.get("From", ""))
#             date_str   = msg.get("Date", "")
#             message_id = msg.get("Message-ID", "")
#             body       = _extract_body(msg)   # already HTML-stripped by _extract_body

#             # Split "Name <addr>" or just "addr"
#             from_name = from_raw
#             from_addr = from_raw
#             if "<" in from_raw and ">" in from_raw:
#                 from_name = from_raw.split("<")[0].strip().strip('"\'')
#                 from_addr = from_raw.split("<")[1].rstrip(">").strip()

#             dt        = _parse_date(date_str)
#             timestamp = dt.timestamp() if dt else 0
#             date_fmt  = dt.strftime("%d %b %Y, %I:%M %p") if dt else date_str
#             is_unread = "\\Seen" not in flags_raw

#             uid_str = uid.decode() if isinstance(uid, bytes) else str(uid)

#             # Store 2000 chars for search accuracy, 150 chars as display snippet
#             return {
#                 "uid":        uid_str,
#                 "subject":    subject,
#                 "from":       from_name or from_addr,
#                 "from_addr":  from_addr,
#                 "date":       date_fmt,
#                 "timestamp":  timestamp,
#                 "body":       body[:2000],
#                 "snippet":    (body[:150].replace("\n", " ") + ("…" if len(body) > 150 else "")),
#                 "is_unread":  is_unread,
#                 "message_id": message_id,
#             }
#         except Exception as e:
#             logger.warning(f"_fetch_one failed for UID {uid}: {e}")
#             return None



"""
skills/email_skill.py — Email Agent (True Agentic Architecture)
================================================================
Architecture:
  EmailTools  — pure low-level IMAP/SMTP operations (no decisions)
  EmailAgent  — plan → execute → observe → retry → chain (all decisions here)
  Skill       — thin adapter wiring agent into Bharvishya's skill registry
 
Agentic behaviours:
  - Automatic search window expansion on no-results (30 → 60 → 90 days)
  - Tool chaining: search → AI summarize in one agent run
  - Tool chaining: fetch original → compose reply → send in one agent run
  - IMAP connection pooling: one connection per multi-step operation
  - Retry with fresh connection on transient IMAP errors
  - Intermediate result observation before deciding next step
"""
 
import asyncio
import email
import imaplib
import logging
import os
import re
import smtplib
import ssl
from datetime import datetime, timedelta
from email.header import decode_header
from email.message import EmailMessage
from typing import Any, Dict, List, Optional
 
import google.generativeai as genai
 
from skills.registry import BaseSkill
 
logger = logging.getLogger("bharvishya.skill.email")
 
# ── Config ────────────────────────────────────────────────────────────────────
SMTP_HOST  = os.getenv("EMAIL_SMTP_HOST",   "smtp.gmail.com")
SMTP_PORT  = int(os.getenv("EMAIL_SMTP_PORT", "465"))
IMAP_HOST  = os.getenv("EMAIL_IMAP_HOST",   "imap.gmail.com")
IMAP_PORT  = int(os.getenv("EMAIL_IMAP_PORT", "993"))
EMAIL_ADDR = os.getenv("EMAIL_ADDRESS",      "")
EMAIL_PASS = os.getenv("EMAIL_APP_PASSWORD", "")
GEMINI_KEY = os.getenv("GEMINI_API_KEY",     "")
GEMINI_MDL = os.getenv("GEMINI_MODEL",       "gemini-3.1-flash-lite-preview")
 
 
# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — Pure parsing helpers (stdlib only, no I/O)
# ─────────────────────────────────────────────────────────────────────────────
 
def _decode_header_val(s: str) -> str:
    if not s:
        return ""
    parts = decode_header(s)
    out = []
    for part, enc in parts:
        if isinstance(part, bytes):
            out.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(str(part))
    return " ".join(out)
 
 
def _strip_html(html: str) -> str:
    """Strip HTML tags → clean readable text. stdlib only, no beautifulsoup."""
    import html as html_mod
    from html.parser import HTMLParser
 
    class _P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts, self._skip = [], False
 
        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "head"):
                self._skip = True
            if tag in ("br", "p", "div", "tr", "li", "h1", "h2", "h3"):
                self.parts.append("\n")
 
        def handle_endtag(self, tag):
            if tag in ("script", "style", "head"):
                self._skip = False
 
        def handle_data(self, data):
            if not self._skip:
                self.parts.append(data)
 
    p = _P()
    try:
        p.feed(html)
    except Exception:
        pass
    text = html_mod.unescape("".join(p.parts))
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()
 
 
def _extract_body(msg: email.message.Message) -> str:
    """
    Extract clean plain text from email message.
    Prefers text/plain. Falls back to text/html → strip tags.
    Without this, HTML-only emails return raw CSS, breaking keyword search.
    """
    plain = html = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if "attachment" in str(part.get("Content-Disposition", "")):
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            charset = part.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
            if ct == "text/plain" and not plain:
                plain = decoded
            elif ct == "text/html" and not html:
                html = decoded
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
            if msg.get_content_type() == "text/html":
                html = decoded
            else:
                plain = decoded
 
    if plain.strip():
        return plain.strip()
    if html.strip():
        return _strip_html(html)
    return ""
 
 
def _parse_date(s: str) -> Optional[datetime]:
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(s)
    except Exception:
        return None
 
 
# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — EmailTools: low-level IMAP/SMTP (no decisions, pure operations)
# ─────────────────────────────────────────────────────────────────────────────
 
class EmailTools:
    """
    Pure tool layer. Every method does exactly one thing and returns a result.
    Never decides what to do next — that is the agent's job.
    All methods are synchronous (called via asyncio.to_thread by the Skill).
    """
 
    def connect_imap(self) -> imaplib.IMAP4_SSL:
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(EMAIL_ADDR, EMAIL_PASS)
        return mail
 
    def fetch_one(self, mail: imaplib.IMAP4_SSL, uid) -> Optional[dict]:
        """Fetch and parse a single email. Returns clean dict or None on failure."""
        try:
            uid_b = uid if isinstance(uid, bytes) else str(uid).encode()
            _, data = mail.uid("fetch", uid_b, "(RFC822 FLAGS)")
            if not data or not data[0]:
                return None
 
            raw   = data[0][1]
            flags = data[0][0].decode() if data[0][0] else ""
            msg   = email.message_from_bytes(raw)
 
            subject    = _decode_header_val(msg.get("Subject", "(No Subject)"))
            from_raw   = _decode_header_val(msg.get("From", ""))
            date_str   = msg.get("Date", "")
            message_id = msg.get("Message-ID", "")
            body       = _extract_body(msg)   # always clean text, never raw HTML
 
            from_name = from_addr = from_raw
            if "<" in from_raw and ">" in from_raw:
                from_name = from_raw.split("<")[0].strip().strip('"\'')
                from_addr = from_raw.split("<")[1].rstrip(">").strip()
 
            dt        = _parse_date(date_str)
            timestamp = dt.timestamp() if dt else 0
            date_fmt  = dt.strftime("%d %b %Y, %I:%M %p") if dt else date_str
            uid_str   = uid.decode() if isinstance(uid, bytes) else str(uid)
 
            return {
                "uid":        uid_str,
                "subject":    subject,
                "from":       from_name or from_addr,
                "from_addr":  from_addr,
                "date":       date_fmt,
                "timestamp":  timestamp,
                "body":       body[:2000],
                "snippet":    body[:150].replace("\n", " ") + ("…" if len(body) > 150 else ""),
                "is_unread":  "\\Seen" not in flags,
                "message_id": message_id,
            }
        except (LookupError, UnicodeDecodeError) as e:
            # "unknown encoding: binary" — email exists in total count but body
            # cannot be parsed. Return a minimal skeleton so it still appears in UI.
            uid_str = uid.decode() if isinstance(uid, bytes) else str(uid)
            logger.warning(f"fetch_one UID={uid_str} encoding error (skipping body): {e}")
            try:
                msg2     = email.message_from_bytes(data[0][1])
                subj     = _decode_header_val(msg2.get("Subject", "(No Subject)"))
                from_raw = _decode_header_val(msg2.get("From", ""))
                date_str = msg2.get("Date", "")
                dt       = _parse_date(date_str)
                return {
                    "uid":        uid_str,
                    "subject":    subj,
                    "from":       from_raw,
                    "from_addr":  from_raw,
                    "date":       dt.strftime("%d %b %Y, %I:%M %p") if dt else date_str,
                    "timestamp":  dt.timestamp() if dt else 0,
                    "body":       "[Email body could not be decoded]",
                    "snippet":    "[Encoding not supported]",
                    "is_unread":  True,
                    "message_id": "",
                }
            except Exception:
                return None
        except Exception as e:
            logger.warning(f"fetch_one UID={uid} failed: {e}")
            return None
 
    def search_uids(self, mail: imaplib.IMAP4_SSL,
                    query: str, days: int, folder: str = "INBOX") -> List[bytes]:
        """
        3-pass UID search. Returns deduplicated list newest-first.
          Pass 1: IMAP SUBJECT search (server-side, instant)
          Pass 2: IMAP FROM search    (server-side, instant)
          Pass 3: client-side body scan after HTML stripping
                  (Gmail IMAP BODY is unreliable, so we do it locally)
        """
        mail.select(folder)
        since       = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
        query_lower = query.lower()
        matched     = set()
 
        # Pass 1 — subject
        try:
            _, r = mail.uid("search", None, f'(SINCE "{since}" SUBJECT "{query}")')
            if r[0]:
                matched.update(r[0].split())
        except Exception:
            pass
 
        # Pass 2 — sender
        try:
            _, r = mail.uid("search", None, f'(SINCE "{since}" FROM "{query}")')
            if r[0]:
                matched.update(r[0].split())
        except Exception:
            pass
 
        # Pass 3 — client-side body scan (cap 150 to bound latency)
        try:
            _, r   = mail.uid("search", None, f'(SINCE "{since}")')
            all_u  = r[0].split()[::-1]
            scan_u = [u for u in all_u if u not in matched][:150]
            for uid in scan_u:
                e = self.fetch_one(mail, uid)
                if not e:
                    continue
                blob = (
                    e["subject"] + " " + e["from"] + " " +
                    e["from_addr"] + " " + e["body"]
                ).lower()
                if query_lower in blob:
                    matched.add(uid)
        except Exception as ex:
            logger.warning(f"body scan failed: {ex}")
 
        result = list(matched)
        try:
            result.sort(key=lambda u: int(u), reverse=True)
        except Exception:
            pass
        return result
 
    def inbox_uids(self, mail: imaplib.IMAP4_SSL,
                   days: int, unread_only: bool = False) -> List[bytes]:
        """
        Return UIDs matching the date+unread criteria, newest first.
        The length of this list is the ONLY reliable total count for the
        given time window. Do NOT use IMAP STATUS UNSEEN — that returns
        all-time unseen count, not windowed, and drifts between calls.
        """
        mail.select("INBOX")
        since = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
        crit  = f'(UNSEEN SINCE "{since}")' if unread_only else f'(SINCE "{since}")'
        _, r  = mail.uid("search", None, crit)
        uids  = r[0].split() if r[0] else []
        return uids[::-1]   # newest first
 
    def fetch_many(self, uids: List, limit: int) -> List[dict]:
        """Fetch N emails in a single IMAP connection — not N connections."""
        if not uids:
            return []
        results = []
        try:
            mail = self.connect_imap()
            mail.select("INBOX")
            for uid in uids[:limit]:
                e = self.fetch_one(mail, uid)
                if e:
                    results.append(e)
            mail.logout()
        except Exception as e:
            logger.error(f"fetch_many: {e}")
        return results
 
    def smtp_send(self, to: str, subject: str, body: str,
                  cc: str = "", reply_msg_id: str = "") -> dict:
        em = EmailMessage()
        em["From"]    = EMAIL_ADDR
        em["To"]      = to
        em["Subject"] = subject
        if cc:
            em["Cc"] = cc
        if reply_msg_id:
            em["In-Reply-To"] = reply_msg_id
            em["References"]  = reply_msg_id
        em.set_content(body)
        ctx = ssl.create_default_context()
        try:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as smtp:
                smtp.login(EMAIL_ADDR, EMAIL_PASS)
                smtp.send_message(em)
            logger.info(f"SMTP → {to}: {subject!r}")
            return {"status": "sent", "to": to, "subject": subject}
        except smtplib.SMTPAuthenticationError:
            return {"error": "SMTP auth failed. Check App Password."}
        except smtplib.SMTPRecipientsRefused:
            return {"error": f"Recipient {to!r} refused."}
        except Exception as e:
            return {"error": f"Send failed: {e}"}
 
    def imap_flag(self, uid: str, flag: str, copy_to: str = "") -> dict:
        """General IMAP flag setter. Used for mark_read and delete."""
        try:
            mail = self.connect_imap()
            mail.select("INBOX")
            if copy_to:
                mail.uid("COPY", uid.encode(), copy_to)
            mail.uid("STORE", uid.encode(), "+FLAGS", flag)
            if copy_to:
                mail.expunge()
            mail.logout()
            return {"status": "ok", "uid": uid}
        except Exception as e:
            return {"error": str(e)}
 
 
# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — Gemini AI summarizer
# ─────────────────────────────────────────────────────────────────────────────
 
def _ai_summarize(emails: List[dict], topic: str) -> str:
    if not GEMINI_KEY or not emails:
        return ""
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel(
        model_name=GEMINI_MDL,
        generation_config=genai.GenerationConfig(temperature=0.3, max_output_tokens=1500),
    )
    digest = ""
    for i, em in enumerate(emails, 1):
        digest += (
            f"\n--- EMAIL {i} ---\n"
            f"From: {em['from']}\n"
            f"Subject: {em['subject']}\n"
            f"Date: {em['date']}\n"
            f"Body: {em['body'][:600]}\n"
        )
    prompt = (
        f"You are an email intelligence assistant. "
        f"User asked about: '{topic}'.\nEmails:\n{digest}\n\n"
        "For EACH email write:\n\n"
        "**[N]. <Subject>** — <Sender> · <Date>\n"
        "📌 **Summary:** 2-3 sentences.\n"
        "🏷️ **Category:** Job Opportunity / Interview Invite / Rejection / "
        "Follow-up / Offer Letter / Newsletter / Other\n"
        "⚡ **Action Required:** Yes or No — if Yes, what action?\n"
        "---\n\n"
        "After all emails:\n### 📊 Overall Insight\n"
        "2-3 sentences: patterns, urgency, recommendation.\n\n"
        "No preamble. Start with EMAIL 1."
    )
    try:
        return model.generate_content(prompt).text.strip()
    except Exception as e:
        logger.error(f"AI summarize error: {e}")
        return ""
 
 
# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — EmailAgent: the brain (plan → execute → observe → retry → chain)
# ─────────────────────────────────────────────────────────────────────────────
 
class EmailAgent:
    """
    True agentic layer. Owns all decision-making.
    EmailTools owns all I/O. EmailAgent owns all logic.
 
    Key agentic patterns implemented:
      1. Retry with expanding window  — run_search auto-expands 30→60→90 days
      2. Tool chaining (search→summarize) — run_summarize is a 2-tool pipeline
      3. Tool chaining (fetch→send)       — run_reply is a 2-tool pipeline
      4. Intermediate observation         — agent checks results before next step
      5. Connection reuse                 — one IMAP connection per multi-step op
      6. Self-correction on IMAP error    — retry with fresh connection
    """
 
    RETRY_WINDOWS = [30, 60, 90]
 
    def __init__(self, tools: EmailTools):
        self.t = tools
 
    # ── read_inbox ─────────────────────────────────────────────────────────────
    def run_read_inbox(self, p: dict) -> dict:
        """
        Fetch emails from inbox.
 
        Two separate numbers are tracked:
          total_in_window  — UIDs the IMAP server says exist in this time window.
                             This is the answer to "how many emails do I have".
                             Reliable because it is a pure IMAP SEARCH count with
                             no fetching involved, so encoding errors cannot affect it.
 
          fetched          — emails we successfully parsed and returned.
                             Always <= total_in_window because some emails have
                             binary/unknown encoding and fetch_one returns None for them.
 
        Previously both numbers were conflated, causing responses like
        "I found 5 emails, you have 190 total" where 190 was unreliable UID count
        and 5 was the fetched count — inconsistent and confusing.
        """
        limit  = int(p.get("limit", 10))
        days   = int(p.get("days", 7))
        unread = bool(p.get("unread", False))
        logger.info(f"[AGENT] read_inbox days={days} limit={limit} unread={unread}")
        try:
            mail = self.t.connect_imap()
            uids = self.t.inbox_uids(mail, days, unread)
 
            # total_in_window: how many emails exist in the window (reliable IMAP count)
            total_in_window = len(uids)
 
            # Fetch only up to `limit` emails for display
            emails = []
            fetch_errors = 0
            for uid in uids[:limit]:
                e = self.t.fetch_one(mail, uid)
                if e:
                    emails.append(e)
                else:
                    fetch_errors += 1
 
            mail.logout()
 
            fetched = len(emails)
            logger.info(
                f"[AGENT] read_inbox → fetched={fetched} total_in_window={total_in_window} "
                f"fetch_errors={fetch_errors} days={days} unread={unread}"
            )
 
            label = "unread" if unread else "total"
            return {
                "status":           "success",
                "emails":           emails,
                "fetched":          fetched,        # how many we are showing
                "total_in_window":  total_in_window, # how many exist in the window
                "label":            label,
                "period":           f"last {days} days",
                # Expose a single clean "count" for synthesis to use — always total_in_window
                # so the answer to "how many" is consistent regardless of limit
                "count":            total_in_window,
            }
        except Exception as e:
            logger.error(f"[AGENT] read_inbox error: {e}")
            return {"error": str(e)}
 
    # ── search (with auto-retry window expansion) ──────────────────────────────
    def run_search(self, p: dict) -> dict:
        """
        Agent retry pattern: if no results at requested window,
        automatically expand search window (30→60→90 days) before giving up.
        """
        query  = p.get("query", "").strip()
        days   = int(p.get("days", 30))
        limit  = int(p.get("limit", 20))
        folder = p.get("folder", "INBOX")
 
        if not query:
            return {"error": "Search query required."}
 
        windows = sorted(set([days] + [w for w in self.RETRY_WINDOWS if w >= days]))
 
        for window in windows:
            logger.info(f"[AGENT] search query={query!r} window={window}d")
            # Execute
            try:
                mail  = self.t.connect_imap()
                uids  = self.t.search_uids(mail, query, window, folder)
                mail.logout()
            except Exception as e:
                logger.warning(f"[AGENT] IMAP error, retrying: {e}")
                try:
                    mail  = self.t.connect_imap()   # self-correct with fresh connection
                    uids  = self.t.search_uids(mail, query, window, folder)
                    mail.logout()
                except Exception as e2:
                    return {"error": f"IMAP failed: {e2}"}
 
            # Observe
            if uids:
                logger.info(f"[AGENT] search found {len(uids)} in {window}d window")
                emails = self.t.fetch_many(uids, limit)
                emails.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
                return {
                    "status": "success", "query": query,
                    "emails": emails, "count": len(emails),
                    "period": f"last {window} days",
                    "window_expanded": window > days,
                }
 
            # Decide: no results → expand window
            logger.info(f"[AGENT] no results at {window}d, expanding...")
 
        return {
            "status": "no_results", "query": query, "emails": [], "count": 0,
            "period": f"last {max(windows)} days",
            "message": (
                f"No emails about '{query}' found even after searching "
                f"{max(windows)} days back."
            ),
        }
 
    # ── summarize: search → observe → AI summarize (tool chain) ───────────────
    def run_summarize(self, p: dict) -> dict:
        """
        Tool chaining pattern:
          Step 1 — run_search  (with built-in retry)
          Step 2 — OBSERVE result
          Step 3 — CHAIN to _ai_summarize
          Step 4 — return unified result (emails + markdown)
 
        This is what turns it from 'tool call' into 'agent behaviour':
        the agent decides to chain two tools based on observing step 1's output.
        """
        query = p.get("query", "").strip()
        days  = int(p.get("days", 30))
        limit = int(p.get("limit", 10))
 
        if not query:
            return {"error": "Provide a topic to search for."}
 
        # Step 1+2: search with agent retry
        logger.info(f"[AGENT] summarize: starting chain for query={query!r}")
        sr = self.run_search({"query": query, "days": days, "limit": limit})
 
        if "error" in sr:
            return sr
 
        emails = sr.get("emails", [])
 
        # Step 2: observe
        if not emails:
            return {
                "status": "no_results", "query": query, "count": 0,
                "message": sr.get("message", f"No emails found about '{query}'."),
                "emails": [], "summary": "",
            }
 
        # Step 3: chain to AI summarizer
        logger.info(f"[AGENT] summarize: chaining {len(emails)} emails to Gemini")
        summary = _ai_summarize(emails, query)
 
        return {
            "status":          "success",
            "query":           query,
            "count":           len(emails),
            "period":          sr.get("period"),
            "window_expanded": sr.get("window_expanded", False),
            "emails":          emails,
            "summary":         summary,
        }
 
    # ── send ───────────────────────────────────────────────────────────────────
    def run_send(self, p: dict) -> dict:
        to      = p.get("to", "").strip()
        subject = p.get("subject", "Message from Bharvishya").strip()
        body    = p.get("body", "").strip()
        cc      = p.get("cc", "")
        if not to:
            return {"error": "Recipient required."}
        if not body:
            return {"error": "Email body cannot be empty."}
        logger.info(f"[AGENT] send to={to!r}")
        result = self.t.smtp_send(to, subject, body, cc)
        if "status" in result:
            result["message"] = f"Email sent to {to}."
        return result
 
    # ── reply: fetch original → observe → compose → send (tool chain) ─────────
    def run_reply(self, p: dict) -> dict:
        """
        Tool chaining pattern:
          Step 1 — fetch original email by UID
          Step 2 — OBSERVE: did we get it?
          Step 3 — CHAIN: build quoted reply body
          Step 4 — CHAIN: send via SMTP
        """
        uid  = str(p.get("uid", "")).strip()
        body = p.get("body", "").strip()
        if not uid:
            return {"error": "Email UID required."}
        if not body:
            return {"error": "Reply body cannot be empty."}
 
        # Step 1: fetch original
        logger.info(f"[AGENT] reply: fetching UID={uid}")
        try:
            mail     = self.t.connect_imap()
            mail.select("INBOX")
            original = self.t.fetch_one(mail, uid.encode())
            mail.logout()
        except Exception as e:
            return {"error": f"Could not fetch email: {e}"}
 
        # Step 2: observe
        if not original:
            return {"error": f"Email UID {uid} not found."}
 
        # Step 3+4: chain → compose quoted reply → send
        logger.info(f"[AGENT] reply: chaining to SMTP → {original['from_addr']}")
        quoted    = "\n".join(f"> {l}" for l in original["body"].splitlines())
        full_body = f"{body}\n\n--- Original Message ---\n{quoted}"
        result    = self.t.smtp_send(
            to          = original["from_addr"],
            subject     = f"Re: {original['subject']}",
            body        = full_body,
            reply_msg_id= original.get("message_id", ""),
        )
        if "status" in result:
            result["message"] = f"Reply sent to {original['from_addr']}."
        return result
 
    # ── delete ─────────────────────────────────────────────────────────────────
    def run_delete(self, p: dict) -> dict:
        uid = str(p.get("uid", "")).strip()
        if not uid:
            return {"error": "Email UID required."}
        logger.info(f"[AGENT] delete UID={uid}")
        r = self.t.imap_flag(uid, "\\Deleted", copy_to="[Gmail]/Trash")
        if r.get("status") == "ok":
            r["message"] = "Email moved to Trash."
        return r
 
    # ── mark_read ──────────────────────────────────────────────────────────────
    def run_mark_read(self, p: dict) -> dict:
        uid = str(p.get("uid", "")).strip()
        if not uid:
            return {"error": "Email UID required."}
        logger.info(f"[AGENT] mark_read UID={uid}")
        r = self.t.imap_flag(uid, "\\Seen")
        if r.get("status") == "ok":
            r["message"] = "Email marked as read."
        return r
 
    # ── check_config ───────────────────────────────────────────────────────────
    def run_check_config(self) -> dict:
        ok = bool(EMAIL_ADDR and EMAIL_PASS)
        return {
            "configured":    ok,
            "email_address": EMAIL_ADDR if ok else None,
            "smtp_host":     SMTP_HOST,
            "imap_host":     IMAP_HOST,
            "message": (
                f"Email agent ready. Connected as {EMAIL_ADDR}."
                if ok else
                "Set EMAIL_ADDRESS and EMAIL_APP_PASSWORD in your .env file."
            ),
        }
 
    # ── Dispatch ───────────────────────────────────────────────────────────────
    def run(self, action: str, params: dict) -> dict:
        return {
            "send":       self.run_send,
            "read_inbox": self.run_read_inbox,
            "search":     self.run_search,
            "summarize":  self.run_summarize,
            "reply":      self.run_reply,
            "delete":     self.run_delete,
            "mark_read":  self.run_mark_read,
        }.get(action, lambda p: {"error": f"Unknown action: {action}"})(params)
 
 
# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 — Skill: thin registry adapter
# ─────────────────────────────────────────────────────────────────────────────
 
class Skill(BaseSkill):
    """
    Thin adapter. Zero logic here — just credential gate,
    async bridge, and result caching for the WebSocket push.
    """
    name = "email_skill"
    description = (
        "Agentic email assistant: send, read inbox, search with auto-retry "
        "window expansion, AI summarize via tool chaining, reply, delete, mark as read."
    )
    actions = [
        "send", "read_inbox", "search", "summarize",
        "reply", "delete", "mark_read", "check_config",
    ]
 
    def __init__(self):
        self._tools       = EmailTools()
        self._agent       = EmailAgent(self._tools)
        self._last_result: dict = {}
 
    async def execute(self, action: str, params: Dict[str, Any]) -> Any:
        if action == "check_config":
            return self._agent.run_check_config()
 
        if not EMAIL_ADDR or not EMAIL_PASS:
            return {
                "error": "Email not configured.",
                "help":  "Set EMAIL_ADDRESS and EMAIL_APP_PASSWORD in your .env file.",
            }
 
        result = await asyncio.to_thread(self._agent.run, action, params)
        self._last_result = result if isinstance(result, dict) else {}
        return result