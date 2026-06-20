"""Video essay co-host app — M3: scripted playback + VAD-triggered improv."""

import json
import os
import queue
import threading
from flask import Flask, Response, request, jsonify, send_from_directory

from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose
from script_parser import parse_script, Turn
from gestures import play_gesture, ListeningAnimator
from tts import speak, generate_audio, play_audio
from llm import generate_improv, check_and_respond
from stt import transcribe
from vad import VADListener

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")
SCRIPT_PATH = os.path.join(SCRIPTS_DIR, "fonts.txt")

app = Flask(__name__, static_folder="static")

# Shared state (protected by state_lock)
state_lock = threading.Lock()
state = {
    "turns": [],
    "index": -1,
    "status": "idle",  # idle | waiting | listening | thinking | playing | done
    "context": "",
}

# Audio + LLM cache: id(turn) -> (text, gesture, audio_array)
# Populated in background after script load. Reactive improv turns are never cached.
_cache: dict[int, tuple[str, str, "np.ndarray"]] = {}
_cache_lock = threading.Lock()

_sse_queues: list[queue.Queue] = []

mini: ReachyMini | None = None
vad: VADListener | None = None
animator: ListeningAnimator | None = None


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def _broadcast(event: str, data: dict):
    msg = f"event: {event}\ndata: {json.dumps(data)}\n\n"
    for q in list(_sse_queues):
        q.put(msg)


def _get_state_snapshot():
    with state_lock:
        turns = state["turns"]
        idx = state["index"]
        return {
            "index": idx,
            "status": state["status"],
            "total": len(turns),
            "turns": [{"speaker": t.speaker, "text": t.text, "gesture": t.gesture} for t in turns],
        }


def _set_status(s: str):
    with state_lock:
        state["status"] = s
    _broadcast("state", _get_state_snapshot())
    if s == "done":
        _rest()


def _rest():
    """Stop animation and return Reachy to neutral resting pose."""
    try:
        animator.stop()
        vad.disable()
        mini.goto_target(
            head=create_head_pose(),
            antennas=[0.0, 0.0],
            body_yaw=0.0,
            duration=0.8,
            method="minjerk",
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Prefetch
# ---------------------------------------------------------------------------

def _prefetch_script(turns: list, context: str = ""):
    """Background thread: pre-generate TTS (and LLM for improv=true) for all REACHY turns."""
    with _cache_lock:
        _cache.clear()

    for i, turn in enumerate(turns):
        if turn.speaker != "REACHY":
            continue
        try:
            if turn.improv:
                line, gesture = generate_improv(turns, i, context)
                audio = generate_audio(line)
                print(f"[prefetch] turn {i} improv → gesture={gesture!r}")
            else:
                line = turn.text
                gesture = turn.gesture
                audio = generate_audio(line)
                print(f"[prefetch] turn {i} scripted TTS done")

            with _cache_lock:
                _cache[id(turn)] = (line, gesture, audio)
        except Exception as e:
            print(f"[prefetch] turn {i} failed: {e}")


# ---------------------------------------------------------------------------
# Playback
# ---------------------------------------------------------------------------

def _play_reachy_turn(turn: Turn):
    """Play a REACHY turn. Uses pre-cached audio/LLM when available. Blocks until done."""
    vad.disable()
    animator.stop()

    # Check cache first
    with _cache_lock:
        cached = _cache.get(id(turn))

    if cached:
        line, gesture, audio = cached
        turn.text = line
        turn.gesture = gesture
        _set_status("playing")
        print(f"[playback] cache hit → gesture={gesture!r}")
    elif turn.improv:
        # Cache miss on a scripted improv turn (prefetch still running) — generate now
        _set_status("thinking")
        with state_lock:
            turns = state["turns"]
            idx = state["index"]
            context = state["context"]
        line, gesture = generate_improv(turns, idx, context)
        turn.text = line
        turn.gesture = gesture
        audio = None  # will use speak() fallback below
        _set_status("playing")
    else:
        gesture = turn.gesture
        audio = None  # will use speak() fallback below
        _set_status("playing")

    # Estimate how long the named gesture lasts so speaking idle waits for it
    gesture_durations = {
        "nod": 1.3, "double_nod": 1.1, "shake": 1.2, "tilt_right": 1.5,
        "tilt_left": 1.5, "look_up": 1.6, "surprised": 0.7, "bow": 1.4,
        "excited": 0.95, "think": 1.9, "idle": 0.4,
    }
    gesture_dur = gesture_durations.get(gesture, 1.2)

    play_gesture(mini, gesture)
    animator.start_speaking(gesture_duration=gesture_dur)
    if audio is not None:
        play_audio(mini, audio)
    else:
        speak(mini, turn.text)
    animator.stop()


def _after_reachy_turn():
    """Called after Reachy finishes speaking. Decide what comes next."""
    with state_lock:
        turns = state["turns"]
        idx = state["index"]
        next_idx = idx + 1

    if next_idx >= len(turns):
        _set_status("done")
        return

    next_turn = turns[next_idx]

    if next_turn.speaker == "HUMAN":
        # Advance display and start listening for the human to finish
        with state_lock:
            state["index"] = next_idx
        _set_status("listening")
        animator.start_listening()
        vad.enable()
    else:
        # Back-to-back REACHY turns — play immediately
        with state_lock:
            state["index"] = next_idx
        _broadcast("state", _get_state_snapshot())
        _play_reachy_turn(next_turn)
        _after_reachy_turn()


def _on_human_speech_end(audio):
    """VAD callback: human finished speaking. Transcribe, check off-script, route."""
    with state_lock:
        if state["status"] != "listening":
            return
        turns = state["turns"]
        current_idx = state["index"]
        context = state["context"]

    # Transcribe what was actually said
    _set_status("thinking")
    actual_text = transcribe(audio)

    # Find the scripted line for the current HUMAN turn
    scripted_text = turns[current_idx].text if current_idx >= 0 else ""

    # Determine next scripted REACHY turn
    next_scripted_idx = current_idx + 1
    while next_scripted_idx < len(turns) and turns[next_scripted_idx].speaker != "REACHY":
        next_scripted_idx += 1
    has_next_reachy = next_scripted_idx < len(turns)

    if not has_next_reachy:
        _set_status("done")
        return

    # Single LLM call: detect off-script AND generate improv line if needed
    off_script, improv_line, improv_gesture = check_and_respond(
        scripted_text, actual_text, turns, next_scripted_idx, context
    )

    if off_script and improv_line:
        # Insert reactive improv turn before the next scripted REACHY turn
        improv_turn = Turn(speaker="REACHY", text=improv_line, gesture=improv_gesture, improv=True)
        with state_lock:
            state["turns"].insert(next_scripted_idx, improv_turn)
            state["index"] = next_scripted_idx
        _broadcast("state", _get_state_snapshot())
        _play_reachy_turn(improv_turn)
        _after_reachy_turn()
    else:
        # On-script — advance to next scripted REACHY turn (likely cache hit)
        with state_lock:
            state["index"] = next_scripted_idx
        _broadcast("state", _get_state_snapshot())
        _play_reachy_turn(turns[next_scripted_idx])
        _after_reachy_turn()


def _advance_thread():
    """Manual Next button: advance one turn regardless of VAD."""
    vad.disable()

    with state_lock:
        turns = state["turns"]
        idx = state["index"]
        next_idx = idx + 1
        if next_idx >= len(turns):
            _set_status("done")
            return
        state["index"] = next_idx

    turn = turns[next_idx]
    _broadcast("state", _get_state_snapshot())

    if turn.speaker == "REACHY":
        _play_reachy_turn(turn)
        _after_reachy_turn()
    else:
        # Human turn — show it and start listening
        _set_status("listening")
        animator.start_listening()
        vad.enable()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/state")
def api_state():
    return jsonify(_get_state_snapshot())


@app.route("/api/next", methods=["POST"])
def api_next():
    with state_lock:
        s = state["status"]
    if s in ("playing", "thinking"):
        return jsonify({"error": "busy"}), 409
    threading.Thread(target=_advance_thread, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/scripts")
def api_scripts_list():
    files = sorted(f for f in os.listdir(SCRIPTS_DIR) if f.endswith(".txt"))
    return jsonify(files)


@app.route("/api/scripts/<path:name>", methods=["GET"])
def api_scripts_get(name):
    path = os.path.join(SCRIPTS_DIR, os.path.basename(name))
    if not os.path.exists(path):
        return jsonify({"error": "not found"}), 404
    with open(path) as f:
        return jsonify({"content": f.read()})


@app.route("/api/scripts/<path:name>", methods=["POST"])
def api_scripts_save(name):
    path = os.path.join(SCRIPTS_DIR, os.path.basename(name))
    content = request.json.get("content", "")
    with open(path, "w") as f:
        f.write(content)
    return jsonify({"ok": True})


@app.route("/api/load", methods=["POST"])
def api_load():
    name = request.json.get("name", "")
    path = os.path.join(SCRIPTS_DIR, os.path.basename(name))
    if not os.path.exists(path):
        return jsonify({"error": "not found"}), 404
    turns, context = parse_script(path)
    with state_lock:
        state["turns"] = turns
        state["index"] = -1
        state["status"] = "waiting"
        state["context"] = context
    _broadcast("state", _get_state_snapshot())
    # Pre-generate TTS (and LLM for improv=true turns) in the background
    threading.Thread(target=_prefetch_script, args=(turns, context), daemon=True).start()
    return jsonify({"ok": True, "turns": len(turns)})


@app.route("/api/events")
def api_events():
    q: queue.Queue = queue.Queue()
    _sse_queues.append(q)

    def stream():
        try:
            yield f"event: state\ndata: {json.dumps(_get_state_snapshot())}\n\n"
            while True:
                msg = q.get()
                yield msg
        finally:
            _sse_queues.remove(q)

    return Response(stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global mini, vad, animator

    turns = parse_script(SCRIPT_PATH)
    with state_lock:
        state["turns"] = turns
        state["index"] = -1
        state["status"] = "waiting"

    print(f"Loaded {len(turns)} turns from {SCRIPT_PATH}")
    print("Connecting to Reachy...")

    vad = VADListener(on_speech_end=_on_human_speech_end)
    vad.start()

    with ReachyMini() as robot:
        mini = robot
        animator = ListeningAnimator(mini)
        mini.media.start_playing()
        print("Connected! Open http://localhost:5005 in your browser.")
        try:
            app.run(host="0.0.0.0", port=5005, threaded=True, use_reloader=False)
        finally:
            vad.stop()
            animator.stop()
            mini.media.stop_playing()
            # Return to neutral pose on exit
            try:
                mini.goto_target(
                    head=create_head_pose(),
                    antennas=[0.0, 0.0],
                    body_yaw=0.0,
                    duration=0.8,
                )
            except Exception:
                pass


if __name__ == "__main__":
    main()
