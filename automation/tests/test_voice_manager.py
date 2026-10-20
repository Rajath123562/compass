"""
Unit tests for COMPASS VoiceManager (Phase 6: Voice I/O).
"""

from unittest.mock import MagicMock, patch
import pytest

from automation.voice_manager import VoiceManager


class TestVoiceManagerWakeWord:
    """Test wake word detection and command string extraction."""

    def test_default_wake_words_match(self):
        vm = VoiceManager()
        
        # Match 'hey compass'
        triggered, cmd = vm.extract_wake_command("Hey Compass, open notepad")
        assert triggered is True
        assert cmd == "open notepad"

        # Match 'compass'
        triggered, cmd = vm.extract_wake_command("Compass launch Chrome")
        assert triggered is True
        assert cmd == "launch Chrome"

        # Match 'ok compass'
        triggered, cmd = vm.extract_wake_command("ok compass: turn up the volume")
        assert triggered is True
        assert cmd == "turn up the volume"

    def test_no_wake_word_match(self):
        vm = VoiceManager()
        triggered, cmd = vm.extract_wake_command("Open the door please")
        assert triggered is False
        assert cmd == "Open the door please"

    def test_custom_wake_words(self):
        vm = VoiceManager(wake_words=["jarvis", "computer"])
        triggered, cmd = vm.extract_wake_command("Jarvis, what is the weather?")
        assert triggered is True
        assert cmd == "what is the weather?"


class TestVoiceManagerTTS:
    """Test Gemini TTS synthesis and Windows SAPI fallback."""

    def test_gemini_tts_synthesis_and_caching(self):
        vm = VoiceManager(api_key="fake-key")

        mock_client = MagicMock()
        mock_part = MagicMock()
        mock_part.inline_data.data = b"RIFF-WAV-AUDIO-DATA"
        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]
        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]

        mock_client.models.generate_content.return_value = mock_response
        vm._client = mock_client

        # First call: synthesizes and caches
        audio = vm.synthesize_gemini_audio("Hello user")
        assert audio == b"RIFF-WAV-AUDIO-DATA"
        assert mock_client.models.generate_content.call_count == 1

        # Second call: returns cached audio without calling client
        cached = vm.synthesize_gemini_audio("Hello user")
        assert cached == b"RIFF-WAV-AUDIO-DATA"
        assert mock_client.models.generate_content.call_count == 1

        # Clearing cache forces regeneration
        vm.clear_cache()
        vm.synthesize_gemini_audio("Hello user")
        assert mock_client.models.generate_content.call_count == 2

    def test_speak_with_sapi_fallback(self):
        # No API key -> falls back to SAPI
        vm = VoiceManager(api_key="")
        mock_sapi = MagicMock()
        vm._sapi_voice = mock_sapi

        res = vm.speak("Task completed successfully")
        assert res["status"] == "spoken"
        assert res["backend"] == "sapi"
        assert mock_sapi.Speak.called


class TestVoiceManagerSTT:
    """Test Gemini Multimodal Audio Transcription."""

    def test_transcribe_audio_empty_bytes(self):
        vm = VoiceManager()
        assert vm.transcribe_audio(b"") == ""

    def test_transcribe_audio_with_gemini(self):
        vm = VoiceManager(api_key="fake-key")
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Click the start button"
        mock_client.models.generate_content.return_value = mock_resp
        vm._client = mock_client

        transcript = vm.transcribe_audio(b"FAKE_AUDIO_SAMPLE", mime_type="audio/wav")
        assert transcript == "Click the start button"
        assert mock_client.models.generate_content.called
