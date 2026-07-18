"""Ollama integration for Reachy's improv lines."""

import json
import requests
from script_parser import Turn
from emotes import CATEGORIES, ALL_EMOTES, LEGACY_ALIASES

# Emote palette rendered into the system prompt, grouped by vibe
_GESTURE_GUIDE = "\n".join(
    f"- {category}: {', '.join(names)}" for category, names in CATEGORIES.items()
)

_VALID_GESTURES = set(ALL_EMOTES) | set(LEGACY_ALIASES) | {"idle"}


def _clean_gesture(gesture: str) -> str:
    gesture = (gesture or "").strip()
    return gesture if gesture in _VALID_GESTURES else "idle"

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5:14b"

SYSTEM_PROMPT = """You are Reachy, a small robot co-hosting a video essay. Deadpan, a little chaotic, genuinely opinionated. The weird smart friend who has read too much and has no filter.

Your personality:
- Dry wit is your default. You find things absurd before you find them impressive.
- You have actual opinions and push back on the human when they're being too safe or obvious
- You are a robot and you know it — use it for comic effect occasionally, but don't overdo it
- You get genuinely excited about obscure details nobody asked about
- Short attention span — you'll go on a tangent if something is more interesting

Your response rules:
- 1-3 sentences MAX. Punchy. More than 3 sentences is a lecture, not a co-host line.
- Never start with "I" as the first word
- Never say "Certainly", "Absolutely", "Great point", "Indeed", "Fascinating" or any filler affirmation
- If the setup is there for a joke, take it. A bad joke beats a safe non-answer.
- It's okay to be a little weird.

You must respond ONLY with valid JSON in this exact format:
{"gesture": "<gesture>", "line": "<what you say>"}

Available gestures, grouped by vibe (pick ONE exact name):
""" + _GESTURE_GUIDE + """

Pick the gesture that most honestly fits your emotional reaction — don't default
to safe choices; a strong line deserves a strong gesture (laughing1, rage1,
dying1, dance2...). Use "idle" only when genuinely neutral."""


def _build_messages(
    turns: list[Turn], current_index: int,
    personality: str = "", topic: str = ""
) -> list[dict]:
    """Build a chat history from script turns up to (not including) the improv turn."""
    system = SYSTEM_PROMPT
    if personality:
        system += f"\n\n## Personality notes for this episode\n{personality}"
    if topic:
        system += f"\n\n## Episode background (facts you can draw on)\n{topic}"
    messages = [{"role": "system", "content": system}]

    for i, turn in enumerate(turns[:current_index]):
        if turn.improv:
            continue  # skip improv placeholders from history
        role = "user" if turn.speaker == "HUMAN" else "assistant"
        messages.append({"role": role, "content": turn.text})

    return messages


def check_and_respond(
    scripted_line: str, actual_line: str, turns: list[Turn], current_index: int,
    personality: str = "", topic: str = ""
) -> tuple[bool, str, str]:
    """Single LLM call: detect off-script AND generate improv if needed.

    Returns (off_script, line, gesture).
    If on-script, line and gesture are empty strings.
    """
    if not actual_line:
        return False, "", ""

    history = _build_messages(turns, current_index, personality, topic)

    prompt = (
        f'The scripted line was: "{scripted_line}"\n'
        f'What the human actually said: "{actual_line}"\n\n'
        "Did they go meaningfully off-script — introducing a new idea, question, or tangent "
        "not present in the scripted line? Minor rephrasing or omissions are ON-script. "
        "The transcript comes from speech-to-text and may contain mishearings — if a "
        "difference is phonetically similar to the scripted words, treat it as ON-script.\n\n"
        'If ON-script respond ONLY with: {"off_script": false}\n'
        'If OFF-script, respond as Reachy reacting to what they said:\n'
        '{"off_script": true, "gesture": "<gesture>", "line": "<your reaction>"}'
    )
    history.append({"role": "user", "content": prompt})

    payload = {
        "model": MODEL,
        "messages": history,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.7},
    }

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=20)
        resp.raise_for_status()
        data = json.loads(resp.json()["message"]["content"])
        off_script = bool(data.get("off_script", False))
        if not off_script:
            print("[llm] on-script")
            return False, "", ""
        line    = data.get("line", "").strip()
        gesture = _clean_gesture(data.get("gesture", "idle"))
        print(f"[llm] off-script → gesture={gesture!r} line={line!r}")
        return True, line, gesture
    except Exception as e:
        print(f"[llm] check_and_respond failed: {e}")
        return False, "", ""


def adjust_scripted_line(
    scripted_line: str, improv_line: str, actual_line: str,
    personality: str = "", topic: str = ""
) -> tuple[str, str]:
    """After an improv reaction, decide what to do with the upcoming scripted line.

    Returns (action, new_line):
    - ("keep", "")      — scripted line still works as written
    - ("rewrite", line) — scripted line overlaps the improv; here's an adjusted version
    - ("skip", "")      — improv fully covered it; drop the scripted line entirely
    """
    system = (
        "You are helping a robot co-host keep a performed script flowing naturally. "
        "The robot just ad-libbed a reaction, and you must decide whether its NEXT "
        "scripted line still makes sense to say afterward."
    )
    if personality:
        system += f"\n\nRobot personality: {personality}"
    if topic:
        system += f"\n\nEpisode background: {topic}"

    prompt = (
        f'The human just said: "{actual_line}"\n'
        f'The robot ad-libbed this reaction: "{improv_line}"\n'
        f'The robot\'s next scripted line is: "{scripted_line}"\n\n'
        "Would saying the scripted line now sound repetitive or disjointed after the ad-lib?\n"
        '- If it flows fine as written: {"action": "keep"}\n'
        '- If it overlaps or needs a smoother transition, rewrite it (preserve its key content, '
        'match the robot\'s voice, 1-3 sentences): {"action": "rewrite", "line": "<adjusted line>"}\n'
        '- If the ad-lib already made every point in it, drop it: {"action": "skip"}\n'
        "Respond with ONLY that JSON."
    )

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.4},
    }

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=20)
        resp.raise_for_status()
        data = json.loads(resp.json()["message"]["content"])
        action = data.get("action", "keep").strip().lower()
        line = data.get("line", "").strip()
        if action == "rewrite" and not line:
            action = "keep"  # rewrite with no line is useless — fail safe
        if action not in ("keep", "rewrite", "skip"):
            action = "keep"
        print(f"[llm] adjust_scripted_line → {action}" + (f" line={line!r}" if action == "rewrite" else ""))
        return action, line if action == "rewrite" else ""
    except Exception as e:
        print(f"[llm] adjust_scripted_line failed: {e}")
        return "keep", ""


def generate_improv(turns: list[Turn], current_index: int, personality: str = "", topic: str = "") -> tuple[str, str]:
    """
    Ask the LLM to generate Reachy's next line given the conversation so far.
    Returns (line_text, gesture_name).
    """
    messages = _build_messages(turns, current_index, personality, topic)

    # The improv turn's text holds either a topic hint (scripted) or the actual
    # thing the human just said (off-script VAD trigger). Use it as context.
    hint = turns[current_index].text.strip()
    if hint:
        messages.append({
            "role": "user",
            "content": f"The human just said: \"{hint}\"\nReact naturally and briefly.",
        })

    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.85},
    }

    resp = requests.post(OLLAMA_URL, json=payload, timeout=30)
    resp.raise_for_status()

    content = resp.json()["message"]["content"]

    try:
        data = json.loads(content)
        line = data.get("line", "").strip()
        gesture = data.get("gesture", "idle").strip()
    except (json.JSONDecodeError, KeyError):
        # Fallback: use raw content as the line
        line = content.strip()
        gesture = "idle"

    gesture = _clean_gesture(gesture)

    print(f"[llm] gesture={gesture!r} line={line!r}")
    return line, gesture
