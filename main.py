# """
# Bharvishya - Production-Grade AI Voice Assistant
# Main FastAPI application entry point
# """

# import asyncio
# import json
# import logging
# import os
# import sys
# from contextlib import asynccontextmanager
# from pathlib import Path

# from dotenv import load_dotenv

# load_dotenv()

# # ── Directory bootstrap (before anything else) ────────────────────────────────
# for _dir in ("logs", "data", "ui"):
#     os.makedirs(_dir, exist_ok=True)

# import uvicorn
# from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import HTMLResponse, JSONResponse
# from fastapi.staticfiles import StaticFiles

# from core.llm import GeminiOrchestrator
# from core.memory import ConversationMemory
# from core.stt import SpeechToText
# from core.tts import TextToSpeech
# from skills.registry import SkillRegistry

# # ── Logging ───────────────────────────────────────────────────────────────────
# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
#     handlers=[
#         logging.StreamHandler(sys.stdout),
#         logging.FileHandler("logs/bharvishya.log", encoding="utf-8"),
#     ],
# )
# logger = logging.getLogger("bharvishya")

# # ── Startup env validation ────────────────────────────────────────────────────
# def _validate_env():
#     warnings = []
#     if not os.getenv("GEMINI_API_KEY"):
#         warnings.append("GEMINI_API_KEY is not set — the LLM will fail to initialize.")
#     if not os.getenv("EMAIL_ADDRESS") or not os.getenv("EMAIL_APP_PASSWORD"):
#         warnings.append("EMAIL_ADDRESS / EMAIL_APP_PASSWORD not set — email skill will be disabled.")
#     if not os.getenv("GOOGLE_CALENDAR_CREDENTIALS"):
#         warnings.append("GOOGLE_CALENDAR_CREDENTIALS not set — calendar will use local SQLite fallback.")
#     for w in warnings:
#         logger.warning(f"[ENV] {w}")


# # ── Lifespan ──────────────────────────────────────────────────────────────────
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     logger.info("Bharvishya starting up...")
#     _validate_env()

#     app.state.memory = ConversationMemory(db_path="data/memory.db")
#     app.state.skill_registry = SkillRegistry()
#     app.state.llm = GeminiOrchestrator(
#         memory=app.state.memory,
#         skill_registry=app.state.skill_registry,
#     )
#     app.state.stt = SpeechToText()
#     app.state.tts = TextToSpeech()
#     logger.info("All systems initialized")
#     yield
#     logger.info("Bharvishya shutting down...")
#     app.state.memory.close()


# # ── App ───────────────────────────────────────────────────────────────────────
# app = FastAPI(
#     title="Bharvishya Voice Assistant",
#     description="Production-grade AI voice assistant powered by Gemini",
#     version="2.0.0",
#     lifespan=lifespan,
# )

# # FIX: Restrict CORS to localhost in development.
# # Change allowed_origins to your production domain before deploying.
# ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8765,http://127.0.0.1:8765").split(",")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=ALLOWED_ORIGINS,
#     allow_methods=["GET", "POST", "DELETE", "PATCH"],
#     allow_headers=["*"],
# )

# # FIX: Guard StaticFiles mount — crashes at startup if `ui/` doesn't exist.
# # Directory is now created above before this line is reached.
# app.mount("/static", StaticFiles(directory="ui"), name="static")


# # ── HTTP Routes ───────────────────────────────────────────────────────────────
# @app.get("/", response_class=HTMLResponse)
# async def root():
#     html_path = Path("ui/index.html")
#     if not html_path.exists():
#         return HTMLResponse(
#             content="<h1>Bharvishya</h1><p>UI not found. Place your index.html in the <code>ui/</code> directory.</p>",
#             status_code=200,
#         )
#     return HTMLResponse(content=html_path.read_text(), status_code=200)


# @app.get("/health")
# async def health():
#     return {"status": "ok", "version": "2.0.0"}


# @app.get("/api/history")
# async def get_history():
#     memory: ConversationMemory = app.state.memory
#     return JSONResponse({"history": memory.get_recent(limit=50)})


# @app.delete("/api/history")
# async def clear_history():
#     app.state.memory.clear_all()
#     return {"status": "cleared"}


# @app.get("/api/tasks")
# async def get_tasks():
#     skill = app.state.skill_registry.get("task_manager")
#     if not skill:
#         return JSONResponse({"tasks": []})
#     return JSONResponse({"tasks": skill.list_tasks()})


# @app.post("/api/tasks")
# async def add_task(body: dict):
#     skill = app.state.skill_registry.get("task_manager")
#     if not skill:
#         return JSONResponse({"error": "Task manager skill not available"}, status_code=503)
#     task = skill.add_task(body.get("text", ""), body.get("priority", "normal"))
#     return JSONResponse({"task": task})


# @app.delete("/api/tasks/{task_id}")
# async def delete_task(task_id: str):
#     skill = app.state.skill_registry.get("task_manager")
#     if skill:
#         skill.delete_task(task_id)
#     return {"status": "deleted"}


# @app.patch("/api/tasks/{task_id}/complete")
# async def complete_task(task_id: str):
#     skill = app.state.skill_registry.get("task_manager")
#     if skill:
#         skill.complete_task(task_id)
#     return {"status": "completed"}


# @app.get("/api/skills")
# async def list_skills():
#     return {"skills": app.state.skill_registry.list_skills()}


# # ── Email Agent REST endpoints ────────────────────────────────────────────────

# @app.get("/api/email/inbox")
# async def email_inbox(days: int = 7, limit: int = 10, unread: bool = False):
#     skill = app.state.skill_registry.get("email_skill")
#     if not skill:
#         return JSONResponse({"error": "Email skill not available"}, status_code=503)
#     return JSONResponse(await skill.execute("read_inbox", {"days": days, "limit": limit, "unread": unread}))


# @app.get("/api/email/search")
# async def email_search(query: str, days: int = 30, limit: int = 15):
#     skill = app.state.skill_registry.get("email_skill")
#     if not skill:
#         return JSONResponse({"error": "Email skill not available"}, status_code=503)
#     return JSONResponse(await skill.execute("search", {"query": query, "days": days, "limit": limit}))


# @app.post("/api/email/summarize")
# async def email_summarize(body: dict):
#     skill = app.state.skill_registry.get("email_skill")
#     if not skill:
#         return JSONResponse({"error": "Email skill not available"}, status_code=503)
#     return JSONResponse(await skill.execute("summarize", {
#         "query": body.get("query", ""),
#         "days":  body.get("days", 5),
#         "limit": body.get("limit", 10),
#     }))


# @app.post("/api/email/send")
# async def email_send(body: dict):
#     skill = app.state.skill_registry.get("email_skill")
#     if not skill:
#         return JSONResponse({"error": "Email skill not available"}, status_code=503)
#     return JSONResponse(await skill.execute("send", body))


# @app.post("/api/email/reply")
# async def email_reply(body: dict):
#     skill = app.state.skill_registry.get("email_skill")
#     if not skill:
#         return JSONResponse({"error": "Email skill not available"}, status_code=503)
#     return JSONResponse(await skill.execute("reply", body))


# @app.delete("/api/email/{uid}")
# async def email_delete(uid: str):
#     skill = app.state.skill_registry.get("email_skill")
#     if not skill:
#         return JSONResponse({"error": "Email skill not available"}, status_code=503)
#     return JSONResponse(await skill.execute("delete", {"uid": uid}))


# @app.patch("/api/email/{uid}/read")
# async def email_mark_read(uid: str):
#     skill = app.state.skill_registry.get("email_skill")
#     if not skill:
#         return JSONResponse({"error": "Email skill not available"}, status_code=503)
#     return JSONResponse(await skill.execute("mark_read", {"uid": uid}))


# @app.get("/api/email/config")
# async def email_config():
#     skill = app.state.skill_registry.get("email_skill")
#     if not skill:
#         return JSONResponse({"error": "Email skill not available"}, status_code=503)
#     return JSONResponse(await skill.execute("check_config", {}))


# # ── WebSocket: Real-time voice/text chat ──────────────────────────────────────
# @app.websocket("/ws")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     llm: GeminiOrchestrator = app.state.llm
#     tts: TextToSpeech = app.state.tts
#     logger.info("WebSocket client connected")

#     try:
#         while True:
#             data = await websocket.receive_json()
#             msg_type = data.get("type")

#             if msg_type == "text_input":
#                 user_text = data.get("text", "").strip()
#                 if not user_text:
#                     continue

#                 await websocket.send_json({"type": "thinking", "status": True})

#                 try:
#                     response_text, skill_used = await llm.process(user_text)
#                     audio_b64 = await tts.synthesize_b64(response_text)

#                     await websocket.send_json({
#                         "type":       "response",
#                         "text":       response_text,
#                         "audio":      audio_b64,
#                         "skill_used": skill_used,
#                         "thinking":   False,
#                     })

#                     # If the email agent ran a summarize/search/read_inbox,
#                     # send the structured email data separately so the UI
#                     # can render rich email cards + markdown summary.
#                     if skill_used == "email_skill":
#                         skill = app.state.skill_registry.get("email_skill")
#                         if skill and hasattr(skill, "_last_result"):
#                             result = skill._last_result
#                             if result and result.get("emails"):
#                                 await websocket.send_json({
#                                     "type":    "email_results",
#                                     "emails":  result.get("emails",  []),
#                                     "summary": result.get("summary", ""),
#                                     "query":   result.get("query",   ""),
#                                     "count":   result.get("count",   0),
#                                     "period":  result.get("period",  ""),
#                                 })
#                 except Exception as e:
#                     logger.error(f"LLM error: {e}")
#                     # FIX: Don't leak raw exception strings to the client.
#                     # Log the full error server-side, send a safe message to the browser.
#                     await websocket.send_json({
#                         "type": "error",
#                         "message": "Something went wrong processing your request. Please try again.",
#                         "thinking": False,
#                     })

#             elif msg_type == "audio_chunk":
#                 stt: SpeechToText = app.state.stt
#                 audio_b64 = data.get("audio", "")
#                 if not audio_b64:
#                     continue
#                 try:
#                     transcript = await stt.transcribe_b64(audio_b64)
#                     if transcript:
#                         await websocket.send_json({
#                             "type": "transcript",
#                             "text": transcript,
#                         })
#                 except Exception as e:
#                     logger.warning(f"STT error: {e}")
#                     # Don't crash the WebSocket connection on STT failure
#                     await websocket.send_json({
#                         "type": "error",
#                         "message": "Could not transcribe audio. Please try speaking again.",
#                         "thinking": False,
#                     })

#             else:
#                 logger.warning(f"Unknown WebSocket message type: {msg_type!r}")

#     except WebSocketDisconnect:
#         logger.info("WebSocket client disconnected")
#     except Exception as e:
#         logger.error(f"WebSocket error: {e}")


# # ── Entry point ───────────────────────────────────────────────────────────────
# if __name__ == "__main__":
#     uvicorn.run(
#         "main:app",
#         host="127.0.0.1",
#         port=8765,
#         reload=True,
#         log_level="info",
#     )



"""
Bharvishya - Production-Grade AI Voice Assistant
Main FastAPI application entry point
"""
 
import asyncio
import uuid
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
 
from dotenv import load_dotenv
 
load_dotenv()
 
# ── Directory bootstrap (before anything else) ────────────────────────────────
for _dir in ("logs", "data", "ui"):
    os.makedirs(_dir, exist_ok=True)
 
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
 
from core.llm import GeminiOrchestrator
from core.memory import ConversationMemory
from core.stt import SpeechToText
from core.tts import TextToSpeech
from skills.registry import SkillRegistry
 
 
memory = ConversationMemory()
skill_registry = SkillRegistry()
 
 
 
# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/bharvishya.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("bharvishya")
 
# ── Startup env validation ────────────────────────────────────────────────────
def _validate_env():
    warnings = []
    if not os.getenv("GEMINI_API_KEY"):
        warnings.append("GEMINI_API_KEY is not set — the LLM will fail to initialize.")
    if not os.getenv("EMAIL_ADDRESS") or not os.getenv("EMAIL_APP_PASSWORD"):
        warnings.append("EMAIL_ADDRESS / EMAIL_APP_PASSWORD not set — email skill will be disabled.")
    if not os.getenv("GOOGLE_CALENDAR_CREDENTIALS"):
        warnings.append("GOOGLE_CALENDAR_CREDENTIALS not set — calendar will use local SQLite fallback.")
    for w in warnings:
        logger.warning(f"[ENV] {w}")
 
 
# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Bharvishya starting up...")
    _validate_env()
 
    app.state.memory = ConversationMemory(db_path="data/memory.db")
    app.state.skill_registry = SkillRegistry()
    app.state.llm = GeminiOrchestrator(
        memory=app.state.memory,
        skill_registry=app.state.skill_registry,
    )
    app.state.stt = SpeechToText()
    app.state.tts = TextToSpeech()
    logger.info("All systems initialized")
    yield
    logger.info("Bharvishya shutting down...")
    app.state.memory.close()
 
 
# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Bharvishya Voice Assistant",
    description="Production-grade AI voice assistant powered by Gemini",
    version="2.0.0",
    lifespan=lifespan,
)
 
# FIX: Restrict CORS to localhost in development.
# Change allowed_origins to your production domain before deploying.
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8765,http://127.0.0.1:8765").split(",")
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "DELETE", "PATCH"],
    allow_headers=["*"],
)
 
# FIX: Guard StaticFiles mount — crashes at startup if `ui/` doesn't exist.
# Directory is now created above before this line is reached.
app.mount("/static", StaticFiles(directory="ui"), name="static")
 
 
# ── HTTP Routes ───────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = Path("ui/index.html")
    if not html_path.exists():
        return HTMLResponse(
            content="<h1>Bharvishya</h1><p>UI not found. Place your index.html in the <code>ui/</code> directory.</p>",
            status_code=200,
        )
    return HTMLResponse(content=html_path.read_text(), status_code=200)
 
 
@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}
 
 
@app.get("/api/history")
async def get_history():
    memory: ConversationMemory = app.state.memory
    return JSONResponse({"history": memory.get_recent(limit=50)})
 
 
@app.delete("/api/history")
async def clear_history():
    app.state.memory.clear_all()
    return {"status": "cleared"}
 
 
@app.get("/api/tasks")
async def get_tasks():
    skill = app.state.skill_registry.get("task_manager")
    if not skill:
        return JSONResponse({"tasks": []})
    return JSONResponse({"tasks": skill.list_tasks()})
 
 
@app.post("/api/tasks")
async def add_task(body: dict):
    skill = app.state.skill_registry.get("task_manager")
    if not skill:
        return JSONResponse({"error": "Task manager skill not available"}, status_code=503)
    task = skill.add_task(body.get("text", ""), body.get("priority", "normal"))
    return JSONResponse({"task": task})
 
 
@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    skill = app.state.skill_registry.get("task_manager")
    if skill:
        skill.delete_task(task_id)
    return {"status": "deleted"}
 
 
@app.patch("/api/tasks/{task_id}/complete")
async def complete_task(task_id: str):
    skill = app.state.skill_registry.get("task_manager")
    if skill:
        skill.complete_task(task_id)
    return {"status": "completed"}
 
 
@app.get("/api/skills")
async def list_skills():
    return {"skills": app.state.skill_registry.list_skills()}
 
 
@app.get("/api/conversations")
def get_conversations():
    return {"conversations": memory.get_conversations()}
 
 
@app.get("/api/conversations/{cid}")
def get_conversation(cid: str):
    return {"messages": memory.get_conversation(cid)}
 
 
 
 
# ── Email Agent REST endpoints ────────────────────────────────────────────────
 
@app.get("/api/email/inbox")
async def email_inbox(days: int = 7, limit: int = 10, unread: bool = False):
    skill = app.state.skill_registry.get("email_skill")
    if not skill:
        return JSONResponse({"error": "Email skill not available"}, status_code=503)
    return JSONResponse(await skill.execute("read_inbox", {"days": days, "limit": limit, "unread": unread}))
 
 
@app.get("/api/email/search")
async def email_search(query: str, days: int = 30, limit: int = 15):
    skill = app.state.skill_registry.get("email_skill")
    if not skill:
        return JSONResponse({"error": "Email skill not available"}, status_code=503)
    return JSONResponse(await skill.execute("search", {"query": query, "days": days, "limit": limit}))
 
 
@app.post("/api/email/summarize")
async def email_summarize(body: dict):
    skill = app.state.skill_registry.get("email_skill")
    if not skill:
        return JSONResponse({"error": "Email skill not available"}, status_code=503)
    return JSONResponse(await skill.execute("summarize", {
        "query": body.get("query", ""),
        "days":  body.get("days", 5),
        "limit": body.get("limit", 10),
    }))
 
 
@app.post("/api/email/send")
async def email_send(body: dict):
    skill = app.state.skill_registry.get("email_skill")
    if not skill:
        return JSONResponse({"error": "Email skill not available"}, status_code=503)
    return JSONResponse(await skill.execute("send", body))
 
 
@app.post("/api/email/reply")
async def email_reply(body: dict):
    skill = app.state.skill_registry.get("email_skill")
    if not skill:
        return JSONResponse({"error": "Email skill not available"}, status_code=503)
    return JSONResponse(await skill.execute("reply", body))
 
 
@app.delete("/api/email/{uid}")
async def email_delete(uid: str):
    skill = app.state.skill_registry.get("email_skill")
    if not skill:
        return JSONResponse({"error": "Email skill not available"}, status_code=503)
    return JSONResponse(await skill.execute("delete", {"uid": uid}))
 
 
@app.patch("/api/email/{uid}/read")
async def email_mark_read(uid: str):
    skill = app.state.skill_registry.get("email_skill")
    if not skill:
        return JSONResponse({"error": "Email skill not available"}, status_code=503)
    return JSONResponse(await skill.execute("mark_read", {"uid": uid}))
 
 
@app.get("/api/email/config")
async def email_config():
    skill = app.state.skill_registry.get("email_skill")
    if not skill:
        return JSONResponse({"error": "Email skill not available"}, status_code=503)
    return JSONResponse(await skill.execute("check_config", {}))
 
 
# ── WebSocket: Real-time voice/text chat ──────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
 
    llm: GeminiOrchestrator = app.state.llm
    tts: TextToSpeech = app.state.tts
    logger.info("WebSocket client connected")
 
    # 🔥 NEW: conversation session id (ONE per connection)
    conversation_id = None
 
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
 
            # ✅ INSIDE loop
            if msg_type == "init":
                incoming_id = data.get("conversation_id")
 
                if incoming_id:
                    conversation_id = incoming_id
                else:
                    import uuid
                    conversation_id = str(uuid.uuid4())[:8]
 
                await websocket.send_json({
                    "type": "conversation_id",
                    "conversation_id": conversation_id
                })
 
            elif msg_type == "text_input":
                user_text = data.get("text", "").strip()
                if not user_text:
                    continue
 
                # Ensure conversation_id always exists — if init was never sent,
                # create one now so memory.add never saves with None
                if not conversation_id:
                    import uuid
                    conversation_id = str(uuid.uuid4())[:8]
                    await websocket.send_json({
                        "type": "conversation_id",
                        "conversation_id": conversation_id
                    })
 
                try:
                    # 🔥 YOUR EXISTING LLM FLOW (UNCHANGED)
                    response_text, skill_used = await llm.process(user_text)
 
                    logger.info(f"[FINAL] Skill used: {skill_used}")
                    logger.info(f"[FINAL] Response: {response_text}")
 
                    # 🔥 TTS (UNCHANGED)
                    audio_b64 = await tts.synthesize_b64(response_text)
 
                    # 🔥 SEND RESPONSE (UNCHANGED)
                    await websocket.send_json({
                        "type":       "response",
                        "text":       response_text,
                        "audio":      audio_b64,
                        "skill_used": skill_used,
                        "thinking":   False,
                    })
 
                    # 🔥 NEW: SAVE WITH conversation_id
                    memory.add(
                        user=user_text,
                        assistant=response_text,
                        skill_used=skill_used,
                        conversation_id=conversation_id
                    )
 
                    # 🔥 EMAIL SPECIAL HANDLING (UNCHANGED)
                    if skill_used == "email_skill":
                        skill = app.state.skill_registry.get("email_skill")
                        if skill and hasattr(skill, "_last_result"):
                            result = skill._last_result
                            if result and result.get("emails"):
                                await websocket.send_json({
                                    "type":    "email_results",
                                    "emails":  result.get("emails",  []),
                                    "summary": result.get("summary", ""),
                                    "query":   result.get("query",   ""),
                                    "count":   result.get("count",   0),
                                    "period":  result.get("period",  ""),
                                })
 
                except Exception as e:
                    logger.error(f"LLM error: {e}")
 
                    await websocket.send_json({
                        "type": "error",
                        "message": "Something went wrong processing your request. Please try again.",
                        "thinking": False,
                    })
 
            elif msg_type == "audio_chunk":
                stt: SpeechToText = app.state.stt
                audio_b64 = data.get("audio", "")
 
                if not audio_b64:
                    continue
 
                try:
                    transcript = await stt.transcribe_b64(audio_b64)
                    if transcript:
                        await websocket.send_json({
                            "type": "transcript",
                            "text": transcript,
                        })
                except Exception as e:
                    logger.warning(f"STT error: {e}")
 
                    await websocket.send_json({
                        "type": "error",
                        "message": "Could not transcribe audio. Please try speaking again.",
                        "thinking": False,
                    })
 
            else:
                logger.warning(f"Unknown WebSocket message type: {msg_type!r}")
 
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
 
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
 
# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8765,
        # reload=True,
        log_level="info",
    )