import re
from dataclasses import dataclass, field
from typing import Literal

@dataclass
class Turn:
    speaker: Literal["HUMAN", "REACHY"]
    text: str
    gesture: str = "idle"
    improv: bool = False


def parse_script(path: str) -> list[Turn]:
    turns = []
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
                continue
            m = header_re.match(line)
            if m:
                flush()
                current_lines = []
                current_speaker = m.group(1)
                attrs_str = m.group(2).strip()
                current_attrs = dict(re.findall(r"(\w+)=(\S+)", attrs_str))
            elif current_speaker:
                current_lines.append(line)

    flush()
    return turns
