import re
from dataclasses import dataclass
from typing import Literal


@dataclass
class Turn:
    speaker: Literal["HUMAN", "REACHY"]
    text: str
    gesture: str = "idle"
    improv: bool = False


def parse_script(path: str) -> tuple[list[Turn], str, str]:
    """Parse a script file.

    Returns (turns, personality, topic).
    - personality: from [PERSONALITY] block (or legacy [CONTEXT])
    - topic: from [TOPIC] block
    """
    turns = []
    personality_lines: list[str] = []
    topic_lines: list[str] = []
    current_section: str | None = None  # "personality" | "topic" | None
    current_speaker = None
    current_attrs: dict = {}
    current_lines: list[str] = []

    def flush():
        if current_speaker and current_lines:
            text = " ".join(" ".join(current_lines).split())
            turns.append(Turn(
                speaker=current_speaker,
                text=text,
                gesture=current_attrs.get("gesture", "idle"),
                improv=current_attrs.get("improv", "false").lower() == "true",
            ))

    header_re = re.compile(r"^\[(HUMAN|REACHY)([^\]]*)\]$")

    with open(path) as f:
        for raw in f:
            line = raw.strip()
            if not line:
                if current_section == "personality":
                    personality_lines.append("")
                elif current_section == "topic":
                    topic_lines.append("")
                continue

            if line in ("[PERSONALITY]", "[CONTEXT]"):
                current_section = "personality"
                continue
            if line == "[TOPIC]":
                current_section = "topic"
                continue

            m = header_re.match(line)
            if m:
                current_section = None
                flush()
                current_lines = []
                current_speaker = m.group(1)
                attrs_str = m.group(2).strip()
                current_attrs = dict(re.findall(r"(\w+)=(\S+)", attrs_str))
            elif current_section == "personality":
                personality_lines.append(line)
            elif current_section == "topic":
                topic_lines.append(line)
            elif current_speaker:
                current_lines.append(line)

    flush()
    return (
        turns,
        "\n".join(personality_lines).strip(),
        "\n".join(topic_lines).strip(),
    )
