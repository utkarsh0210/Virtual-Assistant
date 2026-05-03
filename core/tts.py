# """
# core/tts.py — Text-to-Speech
# Uses edge-tts (Microsoft Azure Neural Voices) — free, high quality, no API key.
# Falls back to pyttsx3 if edge-tts unavailable.
# """

# import asyncio
# import base64
# import io
# import logging
# import os

# logger = logging.getLogger("bharvishya.tts")

# # Voice options: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support
# DEFAULT_VOICE = os.getenv("TTS_VOICE", "en-IN-PrabhatNeural")   # Indian English male
# VOICE_RATE = os.getenv("TTS_RATE", "+5%")   # Slightly faster than default
# VOICE_VOLUME = os.getenv("TTS_VOLUME", "+0%")


# class TextToSpeech:
#     """
#     High-quality TTS using Microsoft edge-tts neural voices.
#     Returns audio as base64 for streaming to the browser, or plays locally.
#     """

#     def __init__(self):
#         self._check_edge_tts()

#     def _check_edge_tts(self):
#         try:
#             import edge_tts  # noqa: F401
#             self.backend = "edge_tts"
#             logger.info(f"TTS backend: edge-tts | voice: {DEFAULT_VOICE}")
#         except ImportError:
#             self.backend = "pyttsx3"
#             logger.warning("edge-tts not found, falling back to pyttsx3")

#     async def synthesize_b64(self, text: str) -> str:
#         """
#         Convert text to speech, return as base64-encoded MP3 string.
#         The frontend decodes and plays this via Web Audio API.
#         """
#         if not text or not text.strip():
#             return ""

#         if self.backend == "edge_tts":
#             return await self._edge_synthesize_b64(text)
#         return await asyncio.to_thread(self._pyttsx3_synthesize_b64, text)

#     async def _edge_synthesize_b64(self, text: str) -> str:
#         import edge_tts
#         communicate = edge_tts.Communicate(
#             text=text,
#             voice=DEFAULT_VOICE,
#             rate=VOICE_RATE,
#             volume=VOICE_VOLUME,
#         )
#         buf = io.BytesIO()
#         async for chunk in communicate.stream():
#             if chunk["type"] == "audio":
#                 buf.write(chunk["data"])
#         return base64.b64encode(buf.getvalue()).decode("utf-8")

#     def _pyttsx3_synthesize_b64(self, text: str) -> str:
#         """Fallback: pyttsx3 doesn't support in-memory synthesis easily, speak directly."""
#         import pyttsx3
#         engine = pyttsx3.init()
#         voices = engine.getProperty("voices")
#         if voices:
#             engine.setProperty("voice", voices[0].id)
#         engine.setProperty("rate", 175)
#         engine.say(text)
#         engine.runAndWait()
#         return ""  # No audio data returned, played directly

#     async def speak(self, text: str):
#         """
#         High-level speak method: synthesizes and plays via system audio.
#         Used for local desktop mode (not browser streaming).
#         """
#         if self.backend == "edge_tts":
#             import edge_tts
#             communicate = edge_tts.Communicate(text=text, voice=DEFAULT_VOICE, rate=VOICE_RATE)
#             with io.BytesIO() as buf:
#                 async for chunk in communicate.stream():
#                     if chunk["type"] == "audio":
#                         buf.write(chunk["data"])
#                 audio_bytes = buf.getvalue()
#             await asyncio.to_thread(self._play_audio_bytes, audio_bytes)
#         else:
#             await asyncio.to_thread(self._pyttsx3_synthesize_b64, text)

#     def _play_audio_bytes(self, audio_bytes: bytes):
#         """Play MP3 bytes via system audio (cross-platform)."""
#         import sys
#         import tempfile
#         import subprocess

#         with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
#             f.write(audio_bytes)
#             tmp_path = f.name

#         try:
#             if sys.platform == "win32":
#                 import winsound
#                 # Convert mp3 to wav for winsound, or use pygame
#                 try:
#                     import pygame
#                     pygame.mixer.init()
#                     pygame.mixer.music.load(tmp_path)
#                     pygame.mixer.music.play()
#                     while pygame.mixer.music.get_busy():
#                         import time; time.sleep(0.1)
#                 except ImportError:
#                     os.startfile(tmp_path)
#             elif sys.platform == "darwin":
#                 subprocess.run(["afplay", tmp_path], check=True)
#             else:
#                 # Linux: try multiple players
#                 for player in ["mpg123", "mpg321", "ffplay", "aplay"]:
#                     try:
#                         subprocess.run([player, tmp_path], check=True, capture_output=True)
#                         break
#                     except (subprocess.CalledProcessError, FileNotFoundError):
#                         continue
#         finally:
#             os.unlink(tmp_path)


"""
core/tts.py — Text-to-Speech
Uses edge-tts (Microsoft Azure Neural Voices) — free, high quality, no API key.
Falls back to pyttsx3 if edge-tts unavailable.
"""

import asyncio
import base64
import io
import logging
import os

logger = logging.getLogger("bharvishya.tts")

# Voice options: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support
DEFAULT_VOICE = os.getenv("TTS_VOICE", "en-IN-PrabhatNeural")   # Indian English male
VOICE_RATE = os.getenv("TTS_RATE", "+5%")   # Slightly faster than default
VOICE_VOLUME = os.getenv("TTS_VOLUME", "+0%")


class TextToSpeech:
    """
    High-quality TTS using Microsoft edge-tts neural voices.
    Returns audio as base64 for streaming to the browser, or plays locally.
    """

    def __init__(self):
        self._check_edge_tts()

    def _check_edge_tts(self):
        try:
            import edge_tts  # noqa: F401
            self.backend = "edge_tts"
            logger.info(f"TTS backend: edge-tts | voice: {DEFAULT_VOICE}")
        except ImportError:
            self.backend = "pyttsx3"
            logger.warning("edge-tts not found, falling back to pyttsx3")

    async def synthesize_b64(self, text: str) -> str:
        """
        Convert text to speech, return as base64-encoded MP3 string.
        The frontend decodes and plays this via Web Audio API.
        """
        if not text or not text.strip():
            return ""

        if self.backend == "edge_tts":
            return await self._edge_synthesize_b64(text)
        return await asyncio.to_thread(self._pyttsx3_synthesize_b64, text)

    async def _edge_synthesize_b64(self, text: str) -> str:
        import edge_tts
        communicate = edge_tts.Communicate(
            text=text,
            voice=DEFAULT_VOICE,
            rate=VOICE_RATE,
            volume=VOICE_VOLUME,
        )
        buf = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def _pyttsx3_synthesize_b64(self, text: str) -> str:
        """Fallback: pyttsx3 doesn't support in-memory synthesis easily, speak directly."""
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        if voices:
            engine.setProperty("voice", voices[0].id)
        engine.setProperty("rate", 175)
        engine.say(text)
        engine.runAndWait()
        return ""  # No audio data returned, played directly

    async def speak(self, text: str):
        """
        High-level speak method: synthesizes and plays via system audio.
        Used for local desktop mode (not browser streaming).
        """
        if self.backend == "edge_tts":
            import edge_tts
            communicate = edge_tts.Communicate(text=text, voice=DEFAULT_VOICE, rate=VOICE_RATE)
            with io.BytesIO() as buf:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        buf.write(chunk["data"])
                audio_bytes = buf.getvalue()
            await asyncio.to_thread(self._play_audio_bytes, audio_bytes)
        else:
            await asyncio.to_thread(self._pyttsx3_synthesize_b64, text)

    def _play_audio_bytes(self, audio_bytes: bytes):
        """Play MP3 bytes via system audio (cross-platform)."""
        import sys
        import tempfile
        import subprocess

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name

        try:
            if sys.platform == "win32":
                import winsound
                # Convert mp3 to wav for winsound, or use pygame
                try:
                    import pygame
                    pygame.mixer.init()
                    pygame.mixer.music.load(tmp_path)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        import time; time.sleep(0.1)
                except ImportError:
                    os.startfile(tmp_path)
            elif sys.platform == "darwin":
                subprocess.run(["afplay", tmp_path], check=True)
            else:
                # Linux: try multiple players
                for player in ["mpg123", "mpg321", "ffplay", "aplay"]:
                    try:
                        subprocess.run([player, tmp_path], check=True, capture_output=True)
                        break
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        continue
        finally:
            os.unlink(tmp_path)