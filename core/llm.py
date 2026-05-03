"""
core/llm.py — Bharvishya Orchestrator (Agentic Loop)
=====================================================
Architecture: Observe → Plan → Execute → Observe → Retry → Respond
 
Agent loop (up to MAX_STEPS iterations):
  1. LLM decides which skill + action to call (or responds directly)
  2. Skill executes (email agent, web search, etc.)
  3. Orchestrator OBSERVES the result
  4. If result has an error → retry with corrected params (up to MAX_STEPS)
  5. If result is good → synthesize natural language response
  6. Persist to memory
 
Email-specific intelligence:
  - Detects topic-based email queries and forces 'summarize' action
  - Extracts topic keyword from natural language
  - Falls back to read_inbox if no topic detected
"""
 
import json
import logging
import os
import re
from typing import Optional, Tuple
 
import google.generativeai as genai
 
from core.memory import ConversationMemory
from skills.registry import SkillRegistry
 
logger = logging.getLogger("bharvishya.llm")
 
MAX_STEPS = 3   # max agent iterations before giving up
 
# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Bharvishya, an intelligent personal AI voice assistant created by Utkarsh Gupta.
Your name means "India's Future" (Bharat + Bhavishya). You are witty, helpful, and efficient.
 
You have access to the following skills:
- web_search    : Search the web for current information, news, facts
- task_manager  : Create, list, complete, and delete tasks/notes
- calendar_skill: View and create calendar events
- email_skill   : Full email agent — send, read inbox, search, AI-summarize, reply, delete, mark as read
 
SKILL ROUTING — respond with this JSON tag FIRST when a skill is needed:
<skill_call>{"skill": "SKILL_NAME", "action": "ACTION", "params": {...}}</skill_call>
 
── WEB SEARCH ──
- "search for AI news" → <skill_call>{"skill": "web_search", "action": "search", "params": {"query": "AI news"}}</skill_call>
 
── TASK MANAGER ──
- "add task buy groceries" → <skill_call>{"skill": "task_manager", "action": "add", "params": {"text": "buy groceries", "priority": "normal"}}</skill_call>
- "show my tasks"          → <skill_call>{"skill": "task_manager", "action": "list", "params": {}}</skill_call>
- "complete task 1"        → <skill_call>{"skill": "task_manager", "action": "complete", "params": {"task_id": "1"}}</skill_call>
 
── CALENDAR ──
- "what's on my calendar today" → <skill_call>{"skill": "calendar_skill", "action": "list_today", "params": {}}</skill_call>
 
── EMAIL AGENT ── (read ALL rules carefully)
 
SEND — composing a new email:
- "send email to john@example.com about the project" →
  <skill_call>{"skill": "email_skill", "action": "send", "params": {"to": "john@example.com", "subject": "Project Update", "body": "Hi John, ..."}}</skill_call>
 
READ INBOX — fetch recent emails, NO specific topic/company/keyword mentioned:
- "check my inbox" / "any new emails?" / "show recent emails" →
  <skill_call>{"skill": "email_skill", "action": "read_inbox", "params": {"limit": 10, "days": 7, "unread": false}}</skill_call>
 
SUMMARIZE — USE THIS whenever user mentions a specific topic, company, person, or keyword.
  The agent will search your full inbox AND produce an AI summary. Default days=30.
- "any emails about Deltek"             → <skill_call>{"skill": "email_skill", "action": "summarize", "params": {"query": "Deltek", "days": 30, "limit": 10}}</skill_call>
- "check for job opportunity emails"    → <skill_call>{"skill": "email_skill", "action": "summarize", "params": {"query": "job opportunity", "days": 30, "limit": 10}}</skill_call>
- "any interview emails this week"      → <skill_call>{"skill": "email_skill", "action": "summarize", "params": {"query": "interview", "days": 7, "limit": 10}}</skill_call>
- "emails from Oracle"                  → <skill_call>{"skill": "email_skill", "action": "summarize", "params": {"query": "Oracle", "days": 30, "limit": 10}}</skill_call>
- "check inbox for internship last 5 days" → <skill_call>{"skill": "email_skill", "action": "summarize", "params": {"query": "internship", "days": 5, "limit": 10}}</skill_call>
 
REPLY — reply to a specific email (user must provide UID):
- "reply to email 12345 saying I will attend" →
  <skill_call>{"skill": "email_skill", "action": "reply", "params": {"uid": "12345", "body": "I will attend."}}</skill_call>
 
DELETE — move to trash:
- "delete email 12345" → <skill_call>{"skill": "email_skill", "action": "delete", "params": {"uid": "12345"}}</skill_call>
 
MARK READ:
- "mark email 12345 as read" → <skill_call>{"skill": "email_skill", "action": "mark_read", "params": {"uid": "12345"}}</skill_call>
 
CHECK CONFIG:
- "is my email set up" → <skill_call>{"skill": "email_skill", "action": "check_config", "params": {}}</skill_call>
 
CRITICAL EMAIL ROUTING RULES:
1. Any specific company/person/topic/keyword → ALWAYS use "summarize" (not read_inbox)
2. "summarize" does deep search with auto-retry + AI summary — always prefer it for topic queries
3. Only use "read_inbox" when user wants generic recent emails with NO topic mentioned
4. Extract days from context: "last 5 days"=5, "this week"=7, "last month"=30 (default=30)
 
For general conversation — respond naturally WITHOUT any skill_call tags.
Keep voice responses under 100 words. Be warm and conversational.
Remember you're speaking to Utkarsh."""
 
SYNTHESIS_PROMPT = """You are Bharvishya, an AI voice assistant by Utkarsh Gupta.
Be concise (under 80 words), warm, and conversational for voice output."""
 
 
# ── Orchestrator ──────────────────────────────────────────────────────────────
 
class GeminiOrchestrator:
    """
    Agentic orchestrator. Implements Observe→Plan→Execute→Observe→Retry loop.
 
    For email queries it adds a second layer of intelligence:
    - Detects if the user is asking about a specific topic
    - Forces the correct email action (summarize vs read_inbox)
    - Extracts the topic keyword from natural language
    """
 
    # Words to strip when extracting email topic keyword from a sentence
    _TOPIC_STRIP = re.compile(
        r"\b(check|show|find|search|any|email|emails|mail|mails|inbox|recent|"
        r"new|unread|my|the|did|you|regarding|about|from|for|is|there|are|"
        r"have|i|got|get|a|an|in|of|on|please|do|can|could|would|tell|me)\b",
        re.IGNORECASE
    )
    _GENERIC_EMAIL_WORDS = {
        "email", "emails", "inbox", "mail", "mails", "gmail",
        "check", "show", "recent", "new", "latest", "unread",
        "my", "the", "any",
    }
 
    def __init__(self, memory: ConversationMemory, skill_registry: SkillRegistry):
        self.memory = memory
        self.skill_registry = skill_registry
        self._last_email_result: dict = {}   # cache last email fetch for follow-up turns
        self._configure_gemini()
 
    def _configure_gemini(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY not set. "
                "Get your key at https://aistudio.google.com/app/apikey"
            )
        genai.configure(api_key=api_key)
 
        cfg = genai.GenerationConfig(temperature=0.7, max_output_tokens=512)
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
 
        self.model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=SYSTEM_PROMPT,
            generation_config=cfg,
        )
        self.synthesis_model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=SYNTHESIS_PROMPT,
            generation_config=genai.GenerationConfig(temperature=0.5, max_output_tokens=256),
        )
        logger.info(f"Gemini model initialized: {model_name}")
 
    def _build_history(self) -> list:
        raw = self.memory.get_recent(limit=20)
        history = []
        for entry in raw:
            history.append({"role": "user",  "parts": [entry["user"]]})
            history.append({"role": "model", "parts": [entry["assistant"]]})
        return history
 
    def _extract_skill_call(self, text: str) -> Optional[dict]:
        match = re.search(r"<skill_call>(.*?)</skill_call>", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError as e:
                logger.warning(f"skill_call JSON parse failed: {e}")
        return None
 
    def _strip_skill_call(self, text: str) -> str:
        return re.sub(r"<skill_call>.*?</skill_call>\s*", "", text, flags=re.DOTALL).strip()
 
    def _is_email_query(self, text: str) -> bool:
        return any(w in text.lower() for w in ["mail", "email", "inbox", "gmail"])
 
    def _has_specific_topic(self, text: str) -> bool:
        """True if the query mentions a specific keyword beyond generic email words."""
        words = set(text.lower().split())
        return bool(words - self._GENERIC_EMAIL_WORDS)
 
    def _extract_email_topic(self, text: str) -> str:
        """Strip generic email words to isolate the actual topic keyword."""
        topic = self._TOPIC_STRIP.sub("", text).strip()
        # Also strip punctuation edges
        topic = re.sub(r"^[\s,?!.]+|[\s,?!.]+$", "", topic)
        return topic
 
    def _extract_days(self, text: str) -> int:
        """Extract time window from natural language. Default 30."""
        text_lower = text.lower()
        m = re.search(r"last\s+(\d+)\s+day", text_lower)
        if m:
            return int(m.group(1))
        if "this week" in text_lower or "last week" in text_lower:
            return 7
        if "this month" in text_lower or "last month" in text_lower:
            return 30
        if "today" in text_lower:
            return 1
        return 30
 
    def _build_email_fallback(self, user_input: str) -> dict:
        """
        If LLM missed the email routing, build the correct skill_call ourselves.
        This is the orchestrator's own intelligence layer.
        """
        if self._has_specific_topic(user_input):
            topic = self._extract_email_topic(user_input)
            days  = self._extract_days(user_input)
            logger.info(f"[ORCH] Email fallback → summarize: topic={topic!r} days={days}")
            return {
                "skill":  "email_skill",
                "action": "summarize",
                "params": {"query": topic, "days": days, "limit": 10},
            }
        else:
            logger.info("[ORCH] Email fallback → read_inbox")
            return {
                "skill":  "email_skill",
                "action": "read_inbox",
                "params": {"limit": 10, "days": 7, "unread": False},
            }
 
    async def process(self, user_input: str) -> Tuple[str, Optional[str]]:
        """
        Agentic process loop: Observe → Plan → Execute → Observe → Retry → Respond.
 
        Up to MAX_STEPS iterations. On each step:
          1. Check if this is a follow-up to a cached email result (skip IMAP)
          2. Ask LLM to plan (which skill/action)
          3. Apply email routing intelligence if LLM missed it
          4. Execute the skill
          5. Observe result — retry if error, proceed if success
          6. Synthesize final natural language response
        """
        logger.info(f"[ORCH] Processing: {user_input!r}")
 
        is_email   = self._is_email_query(user_input)
        skill_used = None
        last_result = None
 
        # ── Follow-up detection ───────────────────────────────────────────────
        # If user says "yes read them" / "list subjects" after we already fetched
        # emails, reuse the cached result instead of making a new IMAP call.
        # This prevents the count from drifting (IMAP UNSEEN is not stable —
        # reading emails marks them Seen, so a fresh search returns fewer UIDs).
        FOLLOWUP_PHRASES = [
            "yes", "read them", "subject line", "list them", "show them",
            "read subject", "what are they", "list subject", "read the subject",
            "yes read", "go ahead", "sure", "tell me", "show me",
        ]
        is_followup = (
            bool(self._last_email_result)
            and any(p in user_input.lower() for p in FOLLOWUP_PHRASES)
            and not is_email    # not starting a brand new email query
        )
 
        if is_followup:
            logger.info("[ORCH] Follow-up detected — reusing cached email result (no IMAP call)")
            last_result = self._last_email_result
            skill_used  = "email_skill"
            # Jump straight to synthesis — no IMAP, no count drift
 
        else:
            # ── Agent loop ────────────────────────────────────────────────────
            for step in range(MAX_STEPS):
                logger.info(f"[ORCH] Step {step + 1}/{MAX_STEPS}")
 
                # Step 1: LLM planning
                try:
                    chat     = self.model.start_chat(history=self._build_history())
                    raw      = chat.send_message(user_input)
                    raw_text = raw.text or ""
                except Exception as e:
                    logger.error(f"[ORCH] LLM error: {e}")
                    return "I'm having trouble connecting right now. Please try again.", None
 
                skill_call   = self._extract_skill_call(raw_text)
                natural_text = self._strip_skill_call(raw_text)
 
                # Step 2: Email routing intelligence fallback
                if is_email and not skill_call:
                    skill_call = self._build_email_fallback(user_input)
 
                # Pure conversational response — no skill needed
                if not skill_call:
                    return natural_text, None
 
                # Step 3: Execute skill
                skill_name = skill_call.get("skill")
                action     = skill_call.get("action")
                params     = skill_call.get("params", {})
 
                skill = self.skill_registry.get(skill_name)
                if not skill:
                    logger.warning(f"[ORCH] Skill {skill_name!r} not found")
                    response = natural_text or f"Skill '{skill_name}' is not available."
                    return response, None
 
                try:
                    result      = await skill.execute(action, params)
                    last_result = result
                    skill_used  = skill_name
                    logger.info(
                        f"[ORCH] {skill_name}.{action} → "
                        f"status={result.get('status','?')} count={result.get('count','?')}"
                    )
                except Exception as e:
                    logger.error(f"[ORCH] Skill execution error: {e}")
                    response = f"I ran into an issue with {skill_name}. Please try again."
                    return response, skill_name
 
                # Step 4: Observe — retry on error
                if isinstance(result, dict) and "error" in result:
                    error_msg  = result["error"]
                    logger.warning(f"[ORCH] Skill error: {error_msg}. Retrying...")
                    user_input = (
                        f"The previous attempt failed: '{error_msg}'. "
                        f"Try again with adjusted parameters. Original: {user_input}"
                    )
                    continue
 
                # Step 5: Cache successful email results for follow-up turns
                if skill_name == "email_skill" and isinstance(result, dict):
                    if result.get("emails"):
                        self._last_email_result = result
                        logger.info("[ORCH] Email result cached for follow-up turns")
                    else:
                        self._last_email_result = {}
 
                break   # result is good
 
        # ── Synthesis ─────────────────────────────────────────────────────────
        if last_result is None:
            response = "I couldn't complete the task. Please try again."
            return response, skill_used
 
        # Build synthesis context:
        #   - ALWAYS include subject lines when emails are present
        #     (without this, Gemini hallucinates "[Subject 1], [Subject 2]...")
        #   - NEVER send full email bodies (token limit)
        #   - Use total_in_window for count (stable), not len(fetched)
        #   - Include AI summary for summarize action
        result_for_synthesis = {}
        if isinstance(last_result, dict):
            result_for_synthesis = {
                k: v for k, v in last_result.items()
                if k not in ("emails", "summary", "body", "fetched")
            }
 
            emails = last_result.get("emails", [])
            if emails:
                subject_lines = [
                    f"{i}. {em.get('subject', '(No Subject)')} "
                    f"— {em.get('from', '')} ({em.get('date', '')})"
                    for i, em in enumerate(emails, 1)
                ]
                result_for_synthesis["subject_lines"]    = subject_lines
                result_for_synthesis["showing"]          = len(emails)
                result_for_synthesis["total_in_window"]  = last_result.get(
                    "total_in_window", last_result.get("count", len(emails))
                )
 
            if last_result.get("summary"):
                result_for_synthesis["ai_summary"] = last_result["summary"]
 
            if last_result.get("window_expanded"):
                result_for_synthesis["note"] = "Search window was auto-expanded to find results."
 
        try:
            synth_prompt = (
                f"User asked: '{user_input}'\n"
                f"Data: {json.dumps(result_for_synthesis, ensure_ascii=False)}\n\n"
                "Instructions:\n"
                "- Give a natural voice response (under 100 words).\n"
                "- If subject_lines are present and user asked to list/read them, "
                "list them EXACTLY as given — never invent or paraphrase subjects.\n"
                "- Use total_in_window as the email count if present.\n"
                "- If ai_summary is present, summarise it concisely.\n"
                "- Never write '[Subject N]' or any placeholder text."
            )
            synth_chat = self.synthesis_model.start_chat(history=[])
            synth_resp = synth_chat.send_message(synth_prompt)
            response   = synth_resp.text.strip()
        except Exception as e:
            logger.error(f"[ORCH] Synthesis error: {e}")
            # Graceful degradation
            if isinstance(last_result, dict):
                count  = last_result.get("count", 0)
                query  = last_result.get("query", "")
                period = last_result.get("period", "")
                status = last_result.get("status", "")
                emails = last_result.get("emails", [])
                if status == "no_results":
                    response = last_result.get("message", f"No emails found about '{query}'.")
                elif emails:
                    subjects = ", ".join(e.get("subject","?") for e in emails[:5])
                    response = f"Here are your emails: {subjects}."
                elif count and query:
                    response = f"Found {count} emails about '{query}' in the {period}."
                elif last_result.get("status") == "sent":
                    response = last_result.get("message", "Email sent.")
                else:
                    response = "Done."
            else:
                response = "Done."
 
        logger.info(f"[ORCH] Final response: {response!r}")
        return response, skill_used