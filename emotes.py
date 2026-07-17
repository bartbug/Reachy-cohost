"""Recorded emote library — 85 pro-recorded moves from Pollen's HuggingFace dataset.

Wraps reachy_mini's RecordedMoves/play_move so emotes behave like our old
hand-coded gestures: named, threaded, with known durations.
"""

import threading

from reachy_mini import ReachyMini
from reachy_mini.motion.recorded_move import RecordedMoves

DATASET = "pollen-robotics/reachy-mini-emotions-library"

# Loaded once at startup (from local HF cache — the daemon pre-downloads it).
_library: RecordedMoves | None = None

# Legacy hand-coded gesture names → closest recorded emote, so old scripts
# and LLM habits keep working.
LEGACY_ALIASES = {
    "nod":        "yes1",
    "double_nod": "enthusiastic1",
    "shake":      "no1",
    "tilt_right": "curious1",
    "tilt_left":  "inquiring1",
    "look_up":    "thoughtful1",
    "surprised":  "surprised1",
    "bow":        "welcoming1",
    "excited":    "enthusiastic2",
    "think":      "thoughtful2",
}

# Curated categories — used for the LLM prompt and the editor dropdown.
# Excludes sleep/system moves (mini-deep-sleep, wake-mini-up, sleep1, waiting).
CATEGORIES = {
    "agree / disagree": ["yes1", "yes_sad1", "no1", "no_excited1", "no_sad1", "understanding1", "understanding2"],
    "curious / thinking": ["curious1", "inquiring1", "inquiring2", "inquiring3", "thoughtful1", "thoughtful2", "uncertain1", "attentive1", "attentive2"],
    "surprise / shock": ["amazed1", "surprised1", "surprised2", "confused1", "incomprehensible2", "lost1", "oops1", "oops2", "fear1", "scared1"],
    "joy / excitement": ["cheerful1", "enthusiastic1", "enthusiastic2", "laughing1", "laughing2", "success1", "success2", "proud1", "proud2", "proud3", "electric1"],
    "warmth": ["loving1", "grateful1", "welcoming1", "welcoming2", "helpful1", "helpful2", "calming1", "serenity1", "relief1", "relief2", "shy1"],
    "displeasure": ["contempt1", "disgusted1", "displeased1", "displeased2", "irritated1", "irritated2", "frustrated1", "furious1", "rage1", "reprimand1", "reprimand2", "reprimand3"],
    "low energy / sad": ["boredom1", "boredom2", "tired1", "exhausted1", "downcast1", "sad1", "sad2", "lonely1", "anxiety1", "resigned1", "uncomfortable1", "indifferent1"],
    "impatience": ["impatient1", "impatient2", "go_away1", "come1"],
    "theatrical": ["dance1", "dance2", "dance3", "dying1", "toc-toc-toc"],
}

ALL_EMOTES = [name for names in CATEGORIES.values() for name in names]


def load_library() -> None:
    """Load the recorded moves library. Call once at startup."""
    global _library
    _library = RecordedMoves(DATASET)
    print(f"[emotes] loaded {len(_library.list_moves())} recorded moves from {DATASET}")


def resolve(name: str) -> str | None:
    """Map a requested gesture/emote name to a real emote name, or None for idle/unknown."""
    name = (name or "").strip()
    name = LEGACY_ALIASES.get(name, name)
    if _library is not None and name in _library.moves:
        return name
    return None


def get_duration(name: str) -> float:
    """Duration in seconds of an emote (after alias resolution). 0.5 fallback."""
    resolved = resolve(name)
    if resolved is None or _library is None:
        return 0.5
    return _library.get(resolved).duration


def stop_current(mini: ReachyMini) -> None:
    """Stop any playing emote WITHOUT touching the audio session.

    NOTE: mini.cancel_move() also calls media stop_playing(), which breaks our
    always-open audio routing — so we set the cancellation flag directly.
    """
    mini._move_cancelled = True


def play_emote(mini: ReachyMini, name: str, blocking: bool = False) -> float:
    """Play a named emote. Returns its duration (0.0 if unknown → no-op).

    Non-blocking by default: runs in a daemon thread like the old gestures.
    """
    resolved = resolve(name)
    if resolved is None or _library is None:
        return 0.0

    move = _library.get(resolved)

    def _run():
        try:
            # Glide into the emote's start pose instead of snapping.
            mini.play_move(move, initial_goto_duration=0.35, sound=False)
        except Exception as e:
            print(f"[emotes] play {resolved!r} failed: {e}")

    if blocking:
        _run()
    else:
        threading.Thread(target=_run, daemon=True).start()
    return move.duration
