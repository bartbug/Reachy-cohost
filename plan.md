# Plan: Reachy Mini Video Essay Co-Host

## What we're building

An app where Reachy Mini acts as a co-host for video essays:
- **Scripted mode**: Load a plain-text script with `[HUMAN]` / `[REACHY]` labeled turns; Reachy performs its lines with TTS (on Reachy's speaker) + synchronized motion
- **Improv mode**: Reachy riffs on-the-fly using a local LLM (Ollama), triggered by voice activity detection (VAD) or a manual button fallback
- **Motion**: Mix — scripted lines get explicit gesture tags in the script; improv lines get LLM-chosen gestures from a palette

## Technical decisions

| Concern | Choice | Rationale |
|---|---|---|
| App type | Python (Reachy Lite, USB) | Local LLM + speaker control needs laptop compute |
| LLM stack | Ollama | Easiest install on macOS, simple HTTP API, great model selection |
| TTS | Kokoro (via `kokoro` pip package) | High quality, runs locally, fast enough for real-time |
| Voice trigger | Silero VAD or WebRTC VAD | Lightweight, runs on CPU, detects human speech end |
| Speaker | Reachy's built-in speaker | Via SDK's audio playback API |
| UI | Simple web UI in `static/` | Script display, advance button, status indicators |

## Architecture

```
Script file (plain text, [HUMAN]/[REACHY] turns)
    ↓
Script Runner
    ├─ Scripted line → TTS → audio bytes → Reachy speaker
    │                        ↓
    │                   Motion planner (gesture tags in script, or default)
    │
    └─ Improv trigger (VAD detects human stopped talking, or button press)
          ↓
       Ollama LLM (context = script so far + system prompt about Reachy's persona)
          ↓
       Generated line → TTS → Reachy speaker + motion (LLM picks gesture from palette)
```

## Script format (plain text)

```
[HUMAN]
Today we're talking about the history of fonts...

[REACHY gesture=nod]
And what a history it is. Did you know the word "typography" comes from Greek?

[HUMAN]
I did not know that. Tell us more.

[REACHY gesture=tilt_right improv=true]
# improv=true means LLM fills in this line at runtime, using this as a prompt hint
```

## Motion gesture palette (v1)

- `nod` — agree, affirm
- `tilt_left` / `tilt_right` — curious, considering
- `look_up` — thinking, recalling
- `shake` — disagree, surprised
- `bow` — greeting, conclusion
- `idle` — default, neutral listening

## Shipped (M1–M4 complete)

- Script format: `[HUMAN]` / `[REACHY gesture=X]` / `[REACHY improv=true]` / `[CONTEXT]`
- TTS through Reachy's speaker via macOS `say`
- Named gesture library (11 gestures) + `ListeningAnimator` (continuous idle/speaking motion)
- VAD → Whisper STT → single LLM call (off-script detection + improv generation combined)
- Pre-cached TTS and LLM for scripted + `improv=true` turns at load time
- Per-script episode context injected into LLM system prompt
- Web UI: structured script editor, perform view, script picker with Edit/Load
- Git version control at github.com/bartbug/Reachy-cohost

## Roadmap

### M5: Session logging
Save a timestamped JSON record for each performance session.

**Contents:**
- Script name, date/time, duration
- Each turn: speaker, text, gesture, type (`scripted` | `improv_scripted` | `improv_reactive`), whether it was triggered by VAD or Next button
- Human turns: what they actually said (Whisper transcript) vs. scripted line, off-script flag

**Approach:**
- `session_logger.py` — `SessionLogger` class, opened at Start, closed at done/shutdown
- Writes to `sessions/<script-name>-<timestamp>.json`
- `_on_human_speech_end` and `_play_reachy_turn` emit events to the logger
- Future: UI to browse/replay past sessions

### M6: Voice quality
Improve TTS voice beyond the default macOS `say` robot voice.

**Quick win — better macOS voices:**
- `say -v Zoe` / `say -v Evan` / `say -v Siri` are significantly more natural
- Per-script voice setting in `[CONTEXT]` block (e.g. `Voice: Zoe`)
- UI voice selector in the context area

**Bigger win — Kokoro TTS (original plan):**
- Kokoro was blocked by a blis C extension build issue early on
- Now that stack is stable, worth a fresh attempt (`pip install kokoro-onnx` avoids the C build)
- Much higher quality, still fully local, ~200ms latency

**Approach:**
- Abstract TTS behind a `tts_backend` setting so `say` and Kokoro are swappable
- Keep `say` as fallback

### M7: Expanded gesture library
Add richer, more expressive motions — potentially using pre-recorded trajectories from Pollen Robotics' HuggingFace datasets.

**Investigation needed:**
- Check pollen-robotics HuggingFace space for published Reachy Mini motion files
- The SDK can replay recorded joint trajectories; if motion datasets exist we can load them without hand-coding
- Identify gaps in current 11-gesture palette (currently missing: laugh/giggle, thinking-while-moving, impatient, celebratory)

**Approach:**
- If HF motion files exist: loader that replays trajectories from file
- If not: hand-code additional gestures in `gestures.py` following existing patterns
- Consider gesture chaining: sequences of named gestures for longer reactions
- LLM gesture palette update to include new gestures once added
