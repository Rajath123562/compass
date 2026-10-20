"""
COMPASS Voice Manager
Provides studio-grade speech output via Gemini 3.8 Flash TTS with offline Windows SAPI fallback,
multimodal speech transcription via Gemini audio processing, and wake-phrase command extraction.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from typing import Any

logger = logging.getLogger(__name__)


class VoiceManager:
    """Manages Text-To-Speech (TTS), Speech-To-Text (STT), and Wake-Word routing."""

    DEFAULT_WAKE_WORDS = ["hey compass", "ok compass", "hi compass", "compass"]

    def __init__(
        self,
        api_key: str | None = None,
        wake_words: list[str] | None = None,
        tts_model: str = "gemini-3.8-flash-tts",
        sapi_voice_rate: int = 0,  # -10 to +10 for SAPI
    ) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.wake_words = [w.lower() for w in (wake_words or self.DEFAULT_WAKE_WORDS)]
        self.tts_model = tts_model
        self.sapi_voice_rate = sapi_voice_rate

        self._audio_cache: dict[str, bytes] = {}
        self._lock = threading.Lock()
        self._client: Any = None
        self._sapi_voice: Any = None

    def _get_gemini_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.api_key:
            return None
        try:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
            return self._client
        except Exception as e:
            logger.warning("Failed to initialize Google GenAI client in VoiceManager: %s", e)
            return None

    def _get_sapi_voice(self) -> Any:
        if self._sapi_voice is not None:
            return self._sapi_voice
        try:
            import win32com.client
            self._sapi_voice = win32com.client.Dispatch("SAPI.SpVoice")
            if hasattr(self._sapi_voice, "Rate"):
                self._sapi_voice.Rate = self.sapi_voice_rate
            return self._sapi_voice
        except Exception as e:
            logger.warning("SAPI SpVoice not available on this platform: %s", e)
            return None

    # ─── Speech Synthesis (TTS) ───────────────────────────────────────────────

    def synthesize_gemini_audio(self, text: str) -> bytes | None:
        """
        Synthesize studio-grade audio using Gemini 3.8 Flash TTS.
        Caches results for repeated phrases.
        """
        clean_text = text.strip()
        if not clean_text:
            return None

        with self._lock:
            if clean_text in self._audio_cache:
                return self._audio_cache[clean_text]

        client = self._get_gemini_client()
        if not client:
            return None

        try:
            # Query Gemini TTS audio modality
            response = client.models.generate_content(
                model=self.tts_model,
                contents=clean_text,
                config={"response_modalities": ["AUDIO"]},
            )

            audio_data: bytes | None = None
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "content") and candidate.content:
                    for part in candidate.content.parts:
                        if hasattr(part, "inline_data") and part.inline_data:
                            data = part.inline_data.data
                            if isinstance(data, bytes):
                                audio_data = data
                            elif isinstance(data, str):
                                import base64
                                audio_data = base64.b64decode(data)
                            break

            if audio_data:
                with self._lock:
                    self._audio_cache[clean_text] = audio_data
                return audio_data
        except Exception as e:
            logger.warning("Gemini TTS synthesis failed: %s", e)

        return None

    def speak_sapi(self, text: str, async_mode: bool = True) -> bool:
        """Speak text through offline Windows SAPI SpVoice."""
        voice = self._get_sapi_voice()
        if not voice:
            return False
        try:
            # 1 = SVSFlagsAsync, 0 = SVSFDefault
            flags = 1 if async_mode else 0
            voice.Speak(text, flags)
            return True
        except Exception as e:
            logger.warning("SAPI voice speaking failed: %s", e)
            return False

    def speak(self, text: str, prefer_gemini: bool = True) -> dict[str, Any]:
        """
        Unified speak API: attempts Gemini studio-grade audio synthesis first,
        falling back seamlessly to offline Windows SAPI.
        """
        clean = text.strip()
        if not clean:
            return {"status": "empty", "backend": "none"}

        if prefer_gemini and self.api_key:
            audio = self.synthesize_gemini_audio(clean)
            if audio:
                return {
                    "status": "synthesized",
                    "backend": "gemini",
                    "model": self.tts_model,
                    "audio_bytes_length": len(audio),
                }

        # Offline Windows SAPI fallback
        success = self.speak_sapi(clean)
        return {
            "status": "spoken" if success else "failed",
            "backend": "sapi" if success else "none",
        }

    # ─── Speech Recognition (STT) ─────────────────────────────────────────────

    def transcribe_audio(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/wav",
    ) -> str:
        """
        Transcribe audio data using Gemini multimodal audio perception.
        """
        if not audio_bytes:
            return ""

        client = self._get_gemini_client()
        if not client:
            return ""

        try:
            from google.genai import types

            audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
            prompt = (
                "Transcribe the following speech recording exactly as spoken. "
                "Output only the transcribed words, without explanations, timestamps, or quotes."
            )

            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=[audio_part, prompt],
            )
            return response.text.strip() if hasattr(response, "text") and response.text else ""
        except Exception as e:
            logger.warning("Gemini audio transcription failed: %s", e)
            return ""

    # ─── Wake Word Detection & Extraction ─────────────────────────────────────

    def extract_wake_command(self, transcript: str) -> tuple[bool, str]:
        """
        Determine if transcript begins with or contains a configured wake word.
        Returns:
            (is_wake_triggered: bool, clean_command: str)
            
        Examples:
            "Hey Compass open Chrome" -> (True, "open Chrome")
            "What is the weather"     -> (False, "What is the weather")
            "Compass, click start"    -> (True, "click start")
        """
        clean = transcript.strip()
        lower = clean.lower()

        # Sort wake words longest-first so "hey compass" matches before "compass"
        sorted_wake = sorted(self.wake_words, key=len, reverse=True)

        for w in sorted_wake:
            pattern = rf"^\s*{re.escape(w)}[\s,:\-–]*(.*)$"
            match = re.match(pattern, lower, flags=re.IGNORECASE)
            if match:
                # Extract remaining portion preserving original case if possible
                matched_prefix_len = len(clean) - len(match.group(1))
                command = clean[matched_prefix_len:].strip()
                return True, command

        return False, clean

    def clear_cache(self) -> None:
        with self._lock:
            self._audio_cache.clear()
