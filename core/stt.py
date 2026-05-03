# """
# core/stt.py — Speech-to-Text
# Supports: Google Speech Recognition (default, no key needed)
#           and Whisper (local, higher accuracy, set USE_WHISPER=true)
# """

# import asyncio
# import base64
# import io
# import logging
# import os
# import tempfile
# from pydub import AudioSegment
# import speech_recognition as sr

# from faster_whisper import WhisperModel
# logger = logging.getLogger("bharvishya.stt")

# USE_WHISPER = os.getenv("USE_WHISPER", "false").lower() == "true"


# class SpeechToText:
#     """
#     Abstraction layer for STT backends.

#     - Default: Google Speech Recognition via `speech_recognition` library
#     - Optional: OpenAI Whisper (local) via `faster-whisper` for offline/accuracy
#     """

#     def __init__(self):
#         if USE_WHISPER:
#             self._init_whisper()
#         else:
#             self._init_google()

#     def _init_google(self):
        
#         self.recognizer = sr.Recognizer()
#         self.recognizer.pause_threshold = 0.8
#         self.recognizer.energy_threshold = 300
#         self.backend = "google"
#         logger.info("STT backend: Google Speech Recognition")

#     def _init_whisper(self):
        
#         model_size = os.getenv("WHISPER_MODEL", "base")
#         self.whisper = WhisperModel(model_size, device="cpu", compute_type="int8")
#         self.backend = "whisper"
#         logger.info(f"STT backend: Whisper ({model_size})")

#     async def transcribe_b64(self, audio_b64: str) -> str:
#         """
#         Transcribe base64-encoded audio (WAV) to text.
#         Runs in a thread to avoid blocking the event loop.
#         """
#         audio_bytes = base64.b64decode(audio_b64)
#         return await asyncio.to_thread(self._transcribe_bytes, audio_bytes)

    

#     async def _google_transcribe(self, audio_bytes: bytes) -> str:

#         try:
#             # Convert any format → WAV
#             audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
#             wav_io = io.BytesIO()
#             audio.export(wav_io, format="wav")
#             wav_io.seek(0)

#             with sr.AudioFile(wav_io) as source:
#                 audio_data = self.recognizer.record(source)

#             return self.recognizer.recognize_google(audio_data, language="en-IN")

#         except Exception as e:
#             logger.error(f"STT conversion error: {e}")
#             return ""

#     def _google_transcribe(self, audio_bytes: bytes) -> str:
#         with io.BytesIO(audio_bytes) as f:
#             with sr.AudioFile(f) as source:
#                 audio = self.recognizer.record(source)
#         try:
#             return self.recognizer.recognize_google(audio, language="en-IN")
#         except sr.UnknownValueError:
#             logger.debug("Google STT: could not understand audio")
#             return ""
#         except sr.RequestError as e:
#             logger.error(f"Google STT request failed: {e}")
#             raise

#     def _whisper_transcribe(self, audio_bytes: bytes) -> str:
#         with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
#             f.write(audio_bytes)
#             tmp_path = f.name
#         try:
#             segments, _ = self.whisper.transcribe(tmp_path, language="en")
#             return " ".join(seg.text.strip() for seg in segments)
#         finally:
#             os.unlink(tmp_path)

#     async def listen_microphone(self) -> str:
#         """
#         Listen from the system microphone and return transcribed text.
#         Used for direct desktop mic input.
#         """
#         return await asyncio.to_thread(self._listen_mic_sync)

#     def _listen_mic_sync(self) -> str:
#         r = sr.Recognizer()
#         r.pause_threshold = 0.8
#         with sr.Microphone() as source:
#             logger.debug("Listening from microphone...")
#             r.adjust_for_ambient_noise(source, duration=0.3)
#             audio = r.listen(source, timeout=10, phrase_time_limit=15)
#         try:
#             text = r.recognize_google(audio, language="en-IN")
#             logger.info(f"Microphone transcript: {text!r}")
#             return text
#         except sr.UnknownValueError:
#             return ""
#         except sr.RequestError as e:
#             logger.error(f"STT error: {e}")
#             raise



"""
core/stt.py — Speech-to-Text
Supports: Google Speech Recognition (default, no key needed)
          and Whisper (local, higher accuracy, set USE_WHISPER=true)
"""

import asyncio
import base64
import logging
import os
import tempfile

import speech_recognition as sr

logger = logging.getLogger("bharvishya.stt")

USE_WHISPER = os.getenv("USE_WHISPER", "false").lower() == "true"


class SpeechToText:
    """
    Abstraction layer for STT backends.

    - Default: Google Speech Recognition via `speech_recognition` library
    - Optional: OpenAI Whisper (local) via `faster-whisper` for offline/accuracy
    """

    def __init__(self):
        if USE_WHISPER:
            self._init_whisper()
        else:
            self._init_google()

    def _init_google(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 0.8
        self.recognizer.energy_threshold = 300
        self.backend = "google"
        logger.info("STT backend: Google Speech Recognition")

    def _init_whisper(self):
        from faster_whisper import WhisperModel
        model_size = os.getenv("WHISPER_MODEL", "base")
        self.whisper = WhisperModel(model_size, device="cpu", compute_type="int8")
        self.backend = "whisper"
        logger.info(f"STT backend: Whisper ({model_size})")

    async def transcribe_b64(self, audio_b64: str) -> str:
        """
        Transcribe base64-encoded audio (WAV) to text.
        Runs in a thread to avoid blocking the event loop.
        """
        if not audio_b64:
            return ""

        try:
            audio_bytes = base64.b64decode(audio_b64)
        except Exception as e:
            logger.error(f"Failed to decode base64 audio: {e}")
            return ""

        return await asyncio.to_thread(self._transcribe_bytes, audio_bytes)

    def _transcribe_bytes(self, audio_bytes: bytes) -> str:
        """
        Dispatch to the correct STT backend.
        This is the missing method that transcribe_b64 calls.
        """
        if self.backend == "whisper":
            return self._whisper_transcribe(audio_bytes)
        return self._google_transcribe(audio_bytes)

    def _google_transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe audio bytes using Google Speech Recognition."""
        import io
        try:
            # Attempt to convert any audio format to WAV via pydub first
            try:
                from pydub import AudioSegment
                audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
                wav_io = io.BytesIO()
                audio.export(wav_io, format="wav")
                wav_io.seek(0)
                source_io = wav_io
            except Exception:
                # Fallback: assume raw WAV bytes
                source_io = io.BytesIO(audio_bytes)

            with sr.AudioFile(source_io) as source:
                audio_data = self.recognizer.record(source)

            return self.recognizer.recognize_google(audio_data, language="en-IN")

        except sr.UnknownValueError:
            logger.debug("Google STT: could not understand audio")
            return ""
        except sr.RequestError as e:
            logger.error(f"Google STT request failed: {e}")
            raise
        except Exception as e:
            logger.error(f"STT conversion error: {e}")
            return ""

    def _whisper_transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe audio bytes using local Whisper model."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name
        try:
            segments, _ = self.whisper.transcribe(tmp_path, language="en")
            return " ".join(seg.text.strip() for seg in segments)
        finally:
            os.unlink(tmp_path)

    async def listen_microphone(self) -> str:
        """
        Listen from the system microphone and return transcribed text.
        Used for direct desktop mic input.
        """
        return await asyncio.to_thread(self._listen_mic_sync)

    def _listen_mic_sync(self) -> str:
        r = sr.Recognizer()
        r.pause_threshold = 0.8
        with sr.Microphone() as source:
            logger.debug("Listening from microphone...")
            r.adjust_for_ambient_noise(source, duration=0.3)
            audio = r.listen(source, timeout=10, phrase_time_limit=15)
        try:
            text = r.recognize_google(audio, language="en-IN")
            logger.info(f"Microphone transcript: {text!r}")
            return text
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            logger.error(f"STT error: {e}")
            raise