# Reachy Mini Local Configuration

## Setup Status
Setup complete: YES — all milestones done

## User Environment
- Robot type: Lite (USB connection)
- OS: macOS (Darwin 25.3.0), Apple Silicon M5 Pro 15-core, 24GB RAM
- Shell: zsh
- Python env tool: venv at `.venv/`
- Project: /Users/christienskousen/Desktop/repos/reachy-hello-world/

## How to run
1. Terminal 1: `source .venv/bin/activate && reachy-mini-daemon`
2. Terminal 2: `source .venv/bin/activate && python3 app.py`
3. Open http://localhost:5005

## Installed packages (venv)
- reachy-mini 1.8.3
- soundfile (AIFF reading — aifc removed in Python 3.13)
- sounddevice (mic capture)
- webrtcvad (patched — see note below)
- faster-whisper (STT, tiny.en model)
- flask, requests, numpy, scipy

## Known quirks / patches
- webrtcvad.py patched: `import pkg_resources` wrapped in try/except (Python 3.13 broke it)
- TTS: macOS `say -r 155 -o /tmp/reachy_tts.aiff` via subprocess, read with soundfile
- `goto_target` default body_yaw is 0.0 (resets body!) — always pass body_yaw=None to preserve it
- Keep `mini.media.start_playing()` open for whole session — stop/start per line breaks audio routing
- VAD calls `self._reset.set()` on `enable()` to flush stale audio from Reachy's speaker bleed

## Project: Video essay co-host
Reachy Mini acts as a robot co-host for video essays. Features:
- Loads plain-text scripts with [HUMAN] / [REACHY gesture=X] / [REACHY improv=true] turns
- Web UI at localhost:5005: script picker, built-in editor, performance view with Next button
- VAD (webrtcvad + sounddevice) detects when human finishes speaking
- Whisper STT (faster-whisper tiny.en) transcribes what was said
- LLM (Ollama qwen2.5:14b) checks if human went off-script; if yes, generates an improv reaction
- Scripted REACHY turns play as written; improv=true turns generate line + gesture via LLM
- TTS via macOS `say`, audio pushed to Reachy's speaker via mini.media.push_audio_sample()

## File map
- `app.py` — Flask server, state machine, routing logic
- `script_parser.py` — parses [HUMAN]/[REACHY] plain text format
- `gestures.py` — named gesture library + ListeningAnimator (idle/speaking modes)
- `tts.py` — macOS say → soundfile → push to Reachy speaker
- `vad.py` — VADListener, records audio, fires callback on end-of-speech
- `stt.py` — faster-whisper transcription
- `llm.py` — Ollama integration (improv generation + off-script detection)
- `scripts/` — script .txt files (fonts.txt is the example)
- `static/index.html` — web UI

## Idle animation (hard-won — don't regress)
- `TICK=0.5s, duration=0.5s` — matching tick/duration = no twitching from interrupted gotos
- `FREQ=2.513 rad/s` — one full left-right swivel every 2.5 seconds
- Pure roll oscillation (±16° listening, ±10° speaking), pitch ~0
- Body counter-swivel: `body_yaw = -sin(t*FREQ) * 0.28 rad` (opposite roll direction)
- `_center()` called before each mode change to snap to known neutral
- Named gestures all set body_yaw=0.0 on first step (prevent collision from drift)
- Micro-reactions use `_go()` which defaults body_yaw=None (safe, doesn't reset body)

## LLM config
- Model: qwen2.5:14b (huge quality upgrade from llama3.2 — keep this)
- Ollama URL: http://localhost:11434/api/chat
- JSON mode for both improv generation and off-script detection
- System prompt: deadpan/chaotic personality, 1-3 sentences max, no filler affirmations

## User preferences
- Wants Reachy to feel like "an ADHD toddler" not a professional TV host
- Prefers motion explanations in plain English (roll/pitch/yaw = ear-to-shoulder / nod / look-left)
- Keeping LLM local for latency and privacy reasons
- New to robotics and local LLM stack — explain concepts as you go
