import subprocess
import tempfile
import time
import numpy as np
import soundfile as sf


def generate_audio(text: str, sample_rate: int = 16000) -> np.ndarray:
    """Synthesize text via macOS `say` and return float32 mono audio array.
    Uses a unique temp file per call so concurrent calls don't collide."""
    with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as f:
        tmp_path = f.name

    subprocess.run(["say", "-r", "155", "-o", tmp_path, text], check=True)

    samples, src_rate = sf.read(tmp_path, dtype="float32", always_2d=False)

    if samples.ndim == 2:
        samples = samples.mean(axis=1)

    if len(samples) == 0:
        print(f"[tts] Warning: empty audio for: {text!r}")
        return np.zeros(0, dtype=np.float32)

    if src_rate != sample_rate:
        target_len = int(len(samples) * sample_rate / src_rate)
        samples = np.interp(
            np.linspace(0, len(samples) - 1, target_len),
            np.arange(len(samples)),
            samples,
        )

    return samples.astype(np.float32)


def play_audio(mini, audio: np.ndarray, sample_rate: int = 16000):
    """Push a pre-generated audio array to Reachy's speaker. Blocks until done."""
    if len(audio) == 0:
        return
    duration = len(audio) / sample_rate
    mini.media.push_audio_sample(audio)
    time.sleep(duration + 0.3)


def speak(mini, text: str, sample_rate: int = 16000):
    """Synthesize and play. Convenience wrapper for non-cached turns."""
    audio = generate_audio(text, sample_rate)
    play_audio(mini, audio, sample_rate)
