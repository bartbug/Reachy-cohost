"""Ollama integration for Reachy's improv lines."""

import json
import requests
from script_parser import Turn

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

Available gestures and when to use them:
- nod: agree, affirm, "yes exactly"
- double_nod: emphatic agreement or enthusiasm
- shake: disagree, amused disbelief, "no no no"
- tilt_right / tilt_left: curious, considering, skeptical
- look_up: recalling, thinking, "hm let me think"
- think: deep pondering, philosophical moment
- surprised: unexpected info, delight, shock
- excited: genuine enthusiasm, can't contain it
- bow: greeting, signing off, formal acknowledgement
- idle: neutral, returning to rest

Pick the gesture that most honestly fits your emotional reaction."""


def _build_messages(turns: list[Turn], current_index: int) -> list[dict]:
    """Build a chat history from script turns up to (not including) the improv turn."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for i, turn in enumerate(turns[:current_index]):
        if turn.improv:
            continue  # skip improv placeholders from history
        role = "user" if turn.speaker == "HUMAN" else "assistant"
        # For assistant turns, strip the JSON wrapper since those were real lines
        messages.append({"role": role, "content": turn.text})

    return messages


def is_off_script(scripted_line: str, actual_line: str) -> bool:
    """Ask the LLM whether the human went meaningfully off-script."""
    if not actual_line:
        return False

    prompt = f"""You are judging whether a speaker went significantly off-script.

Scripted line: "{scripted_line}"
What they actually said: "{actual_line}"

Did they introduce a meaningfully new idea, question, or tangent not present in the scripted line?
Minor rephrasing or omissions do NOT count as off-script.
Respond with JSON: {{"off_script": true}} or {{"off_script": false}}"""

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.0},
    }

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=15)
        resp.raise_for_status()
        data = json.loads(resp.json()["message"]["content"])
        result = bool(data.get("off_script", False))
        print(f"[llm] off_script={result}")
        return result
    except Exception as e:
        print(f"[llm] off_script check failed: {e}")
        return False


def generate_improv(turns: list[Turn], current_index: int) -> tuple[str, str]:
    """
    Ask the LLM to generate Reachy's next line given the conversation so far.
    Returns (line_text, gesture_name).
    """
    messages = _build_messages(turns, current_index)

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

    valid_gestures = {"nod", "double_nod", "shake", "tilt_right", "tilt_left",
                      "look_up", "surprised", "bow", "excited", "think", "idle"}
    if gesture not in valid_gestures:
        gesture = "idle"

    print(f"[llm] gesture={gesture!r} line={line!r}")
    return line, gesture
