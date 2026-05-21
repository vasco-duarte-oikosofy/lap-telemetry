"""TTS adapter for the race coach.

Provides abstract base class and concrete implementations:
- KokoroAdapter: local ONNX TTS with natural intonation (primary engine)
- Pyttsx3Adapter: uses pyttsx3/SAPI as zero-install fallback (Windows-only)
- FileAdapter: writes text to a file (for testing without speakers)
"""
from __future__ import annotations

import logging
import os
import struct
import subprocess
import tempfile
import wave
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .coach_config import TTSConfig

log = logging.getLogger(__name__)


class TTSAdapter(ABC):
    """Abstract base class for TTS adapters."""

    @abstractmethod
    def speak(self, text: str) -> None:
        """Synthesize and play (or save) the given text.

        Args:
            text: The text to speak.
        """


class KokoroAdapter(TTSAdapter):
    """TTS adapter using Kokoro ONNX engine.

    Kokoro produces natural-sounding speech with proper intonation.
    This is the primary TTS engine for the race coach.
    """

    def __init__(self, config: TTSConfig) -> None:
        self._model_path = config.kokoro_model
        self._voices_path = config.kokoro_voices
        self._voice = config.kokoro_voice
        self._speed = config.kokoro_speed
        self._kokoro = None  # Lazy-loaded

    def _ensure_loaded(self) -> None:
        """Lazy-load the Kokoro model on first use."""
        if self._kokoro is not None:
            return
        try:
            from kokoro_onnx import Kokoro  # type: ignore[import-untyped]
        except ImportError as e:
            raise RuntimeError(
                "kokoro-onnx is not installed. "
                "Install it with: pip install kokoro-onnx"
            ) from e

        model = Path(self._model_path)
        voices = Path(self._voices_path)
        if not model.exists():
            raise RuntimeError(
                f"Kokoro model not found: {model}. "
                "Follow docs/TTS_SETUP.md to set up TTS voices."
            )
        if not voices.exists():
            raise RuntimeError(
                f"Kokoro voices file not found: {voices}. "
                "Follow docs/TTS_SETUP.md to set up TTS voices."
            )

        log.info("Loading Kokoro model: %s", model)
        self._kokoro = Kokoro(str(model), str(voices))
        log.info("Kokoro model loaded, voice=%s, speed=%.2f", self._voice, self._speed)

    def speak(self, text: str) -> None:
        """Synthesize text with Kokoro and play the resulting audio."""
        self._ensure_loaded()
        samples, sample_rate = self._kokoro.create(
            text, voice=self._voice, speed=self._speed
        )
        log.info("Kokoro synthesized %d chars (%d samples)", len(text), len(samples))
        self._play_audio(samples, sample_rate)

    def _play_audio(self, samples: list[float], sample_rate: int) -> None:
        """Play audio samples through sounddevice or platform fallback."""
        import numpy as np

        try:
            import sounddevice as sd  # type: ignore[import-untyped]
            audio = np.array(samples, dtype=np.float32)
            sd.play(audio, sample_rate)
            sd.wait()
            log.debug("Playback finished via sounddevice")
            return
        except ImportError:
            log.debug("sounddevice not available, trying WAV fallback")

        # Fallback: write WAV and play with platform player
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = Path(tmp.name)

        try:
            # Convert float samples to 16-bit PCM
            pcm = [int(max(-1.0, min(1.0, s)) * 32767) for s in samples]
            with wave.open(str(wav_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(struct.pack(f"<{len(pcm)}h", *pcm))

            self._play_wav_fallback(wav_path)
        finally:
            if wav_path.exists():
                wav_path.unlink()

    def _play_wav_fallback(self, wav_path: Path) -> None:
        """Play a WAV file using the platform's built-in audio player."""
        import platform

        system = platform.system()
        if system == "Darwin":
            subprocess.run(["afplay", str(wav_path)], check=True, timeout=30)
        elif system == "Windows":
            ps_cmd = f'(New-Object Media.SoundPlayer "{wav_path}").PlaySync()'
            subprocess.run(
                ["powershell", "-Command", ps_cmd],
                check=True, timeout=30,
            )
        elif system == "Linux":
            subprocess.run(["aplay", str(wav_path)], check=True, timeout=30)
        else:
            log.warning("No audio playback available on %s", system)


class Pyttsx3Adapter(TTSAdapter):
    """TTS adapter using pyttsx3/SAPI (zero-install Windows fallback)."""

    def __init__(self) -> None:
        try:
            import pyttsx3  # type: ignore[import-untyped]
            self._engine = pyttsx3.init()
        except ImportError as e:
            raise RuntimeError(
                "pyttsx3 is not installed. Install it with: pip install pyttsx3"
            ) from e

    def speak(self, text: str) -> None:
        """Speak text using pyttsx3."""
        self._engine.say(text)
        self._engine.runAndWait()
        log.info("Spoke %d chars via pyttsx3", len(text))


class FileAdapter(TTSAdapter):
    """TTS adapter that writes text to a file (for testing without speakers).

    Writes the text as UTF-8 content to the specified output path.
    Does not synthesize real audio — purely for validation and CI.
    """

    def __init__(self, output_path: Path | None = None) -> None:
        self._output_path = output_path or Path("coach_output.wav")

    def speak(self, text: str) -> None:
        """Write text to the output file."""
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        self._output_path.write_text(text, encoding="utf-8")
        log.info("Wrote %d chars to %s", len(text), self._output_path)


def create_adapter(config: TTSConfig) -> TTSAdapter:
    """Create a TTS adapter based on configuration.

    Args:
        config: TTS configuration specifying engine and settings.

    Returns:
        A TTSAdapter instance.

    Raises:
        ValueError: If the engine name is unknown.
    """
    engine = config.engine.lower()

    if engine == "kokoro":
        return KokoroAdapter(config)
    elif engine == "pyttsx3":
        return Pyttsx3Adapter()
    elif engine == "file":
        return FileAdapter(output_path=Path(config.output_file))
    else:
        raise ValueError(f"Unknown TTS engine: {engine!r}")