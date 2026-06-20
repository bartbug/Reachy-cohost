"""Voice activity detection — records human speech and fires a callback with the audio."""

import threading
import collections
import numpy as np
import sounddevice as sd
import webrtcvad

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_MS / 1000)  # 480 samples
VAD_AGGRESSIVENESS = 2

MIN_SPEECH_FRAMES = 10         # ~300ms before we consider it real speech
SILENCE_FRAMES_TO_TRIGGER = 25 # ~750ms of silence after speech → end of utterance


class VADListener:
    """Runs a mic listener in a background thread.
    Calls on_speech_end(audio: np.ndarray) with the recorded float32 16kHz audio."""

    def __init__(self, on_speech_end, aggressiveness=VAD_AGGRESSIVENESS):
        self._vad = webrtcvad.Vad(aggressiveness)
        self._on_speech_end = on_speech_end
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._enabled = threading.Event()
        self._reset = threading.Event()

    def enable(self):
        self._reset.set()   # flush stale audio state before re-enabling
        self._enabled.set()

    def disable(self):
        self._enabled.clear()

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _run(self):
        ring = collections.deque(maxlen=SILENCE_FRAMES_TO_TRIGGER)
        speech_frame_count = 0
        in_speech = False
        recorded: list[np.ndarray] = []
        leftover = np.array([], dtype=np.int16)

        def callback(indata, frames, time_info, status):
            nonlocal leftover, speech_frame_count, in_speech

            if self._reset.is_set():
                self._reset.clear()
                ring.clear()
                recorded.clear()
                speech_frame_count = 0
                in_speech = False
                leftover = np.array([], dtype=np.int16)

            pcm = (indata[:, 0] * 32767).astype(np.int16)
            combined = np.concatenate([leftover, pcm])

            i = 0
            while i + FRAME_SAMPLES <= len(combined):
                frame = combined[i:i + FRAME_SAMPLES]
                is_speech = self._vad.is_speech(frame.tobytes(), SAMPLE_RATE)
                ring.append(is_speech)

                if is_speech:
                    if not in_speech:
                        in_speech = True
                    speech_frame_count += 1
                    recorded.append(frame.astype(np.float32) / 32767.0)

                if (
                    in_speech
                    and speech_frame_count >= MIN_SPEECH_FRAMES
                    and len(ring) == SILENCE_FRAMES_TO_TRIGGER
                    and not any(ring)
                    and self._enabled.is_set()
                ):
                    audio = np.concatenate(recorded) if recorded else np.array([], dtype=np.float32)
                    in_speech = False
                    speech_frame_count = 0
                    ring.clear()
                    recorded.clear()
                    self._enabled.clear()
                    threading.Thread(
                        target=self._on_speech_end, args=(audio,), daemon=True
                    ).start()

                i += FRAME_SAMPLES

            leftover = combined[i:]

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=FRAME_SAMPLES,
            callback=callback,
        ):
            self._stop_event.wait()
