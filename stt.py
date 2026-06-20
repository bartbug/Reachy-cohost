"""Speech-to-text via faster-whisper (local, runs on CPU/Metal)."""

import numpy as np
from faster_whisper import WhisperModel

_model: WhisperModel | None = None

def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        print("[stt] Loading Whisper model (first run may download ~150MB)…")
        # tiny.en is fast enough for real-time on Apple Silicon
        _model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
        print("[stt] Model ready.")
    return _model


def transcribe(audio: np.ndarray, sample_rate: int = 16000) -> str:
    """Transcribe float32 mono audio to text. Returns empty string on failure."""
    if len(audio) < sample_rate * 0.3:  # less than 300ms — probably noise
        return ""
    model = _get_model()
    segments, _ = model.transcribe(audio, language="en", beam_size=1, vad_filter=True)
    text = " ".join(s.text.strip() for s in segments).strip()
    print(f"[stt] transcribed: {text!r}")
    return text
