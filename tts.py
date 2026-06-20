import subprocess
import time
import numpy as np
import soundfile as sf


def speak(mini, text: str, sample_rate: int = 16000):
    """Synthesize text via macOS `say` and play through Reachy's speaker. Blocks until done."""
    tmp_path = "/tmp/reachy_tts.aiff"

    subprocess.run(
        ["say", "-r", "155", "-o", tmp_path, text],
        check=True,
    )

    samples, src_rate = sf.read(tmp_path, dtype="float32", always_2d=False)

    if samples.ndim == 2:
        samples = samples.mean(axis=1)

    if len(samples) == 0:
        print(f"[tts] Warning: empty audio for: {text!r}")
        return

    if src_rate != sample_rate:
        target_len = int(len(samples) * sample_rate / src_rate)
        samples = np.interp(
            np.linspace(0, len(samples) - 1, target_len),
            np.arange(len(samples)),
            samples,
        )

    audio = samples.astype(np.float32)
    duration = len(audio) / sample_rate

    mini.media.push_audio_sample(audio)
    time.sleep(duration + 0.3)
