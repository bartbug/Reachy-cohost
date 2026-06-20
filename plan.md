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

## Milestones

### M1: Environment + hello world (do first)
- [ ] Install Ollama + pull a model (llama3.2 or similar)
- [ ] Confirm Reachy SDK installed and robot connects
- [ ] Confirm Reachy speaker works (play a test sound)
- [ ] Install Kokoro TTS, generate a test phrase

### M2: Script playback (scripted lines only)
- [ ] Script parser (plain text → turn list)
- [ ] TTS → Reachy speaker pipeline
- [ ] Motion gesture executor
- [ ] Manual advance button (web UI)

### M3: Improv
- [ ] VAD (detect human speech end)
- [ ] Ollama integration (streaming response)
- [ ] LLM picks gesture from palette
- [ ] Blend improv lines back into script context

### M4: Polish
- [ ] Script editor in UI
- [ ] Gesture preview / override
- [ ] Latency tuning

## Open questions (deferred, not blocking M1)
- How much creative latitude does the LLM get in improv? (tone, length, staying on-topic)
- Should Reachy's persona/voice be configurable per-script or global?
