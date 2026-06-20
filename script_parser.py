import re
from dataclasses import dataclass, field
from typing import Literal

@dataclass
class Turn:
    speaker: Literal["HUMAN", "REACHY"]
    text: str
    gesture: str = "idle"
    improv: bool = False


def parse_script(path: str) -> tuple[list[Turn], str]:
    """Parse a script file. Returns (turns, context) where context is the
    freeform text from an optional [CONTEXT] block at the top of the file."""
    turns = []
    context_lines: list[str] = []
    in_context = False
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
                if in_context:
                    context_lines.append("")
                continue
            if line == "[CONTEXT]":
                in_context = True
                continue
            m = header_re.match(line)
            if m:
                in_context = False
                flush()
                current_lines = []
                current_speaker = m.group(1)
                attrs_str = m.group(2).strip()
                current_attrs = dict(re.findall(r"(\w+)=(\S+)", attrs_str))
            elif in_context:
                context_lines.append(line)
            elif current_speaker:
                current_lines.append(line)

    flush()
    context = "\n".join(context_lines).strip()
    return turns, context
