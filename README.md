# gemma4_tribe

A parallel persona engine built on Google Gemma 4, submitted to the **Gemma 4 Challenge** on dev.to (Build track).

## Architecture

```
User input
    │
    ├──► 🌕 Mochi  (gemma4:e2b) — emotion & empathy     ─┐
    ├──► 🗓️  Jun    (gemma4:e2b) — logic & expression    ─┼── parallel
    └──► 🗝️  Uruu   (gemma4:e2b) — analysis & observation ─┘
                                                            │
                                                            ▼
                                              📅 Koyomi (gemma4:e4b)
                                              Integration leader
                                                            │
                                                            ▼
                                                     Final response
```

- **E2B × 3** workers run in parallel via `asyncio.gather`
- **E4B × 1** leader integrates all three reports
- HTTP API only — no CLI subprocess, no spinner artifacts

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com/) running locally on port 11434
- Models pulled:
  ```
  ollama pull gemma4:e2b
  ollama pull gemma4:e4b
  ```
- For true parallel E2B requests, set:
  ```
  OLLAMA_NUM_PARALLEL=3
  ```

## Install

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Single question
python main.py "I'm feeling stuck on a project."

# Interactive mode
python main.py
```

## Personas

| Name | Model | Role | Trait |
|------|-------|------|-------|
| 📅 Koyomi | gemma4:e4b | Integration leader | Calm, occasionally clumsy |
| 🌕 Mochi  | gemma4:e2b | Emotion & empathy | Overdramatic, high connection |
| 🗓️ Jun    | gemma4:e2b | Logic & expression | Verbose, precise |
| 🗝️ Uruu   | gemma4:e2b | Analysis & observation | Quietly mischievous |

## Performance (RTX 4070 Ti / 48GB RAM)

| Phase | Time |
|-------|------|
| Workers (E2B × 3 parallel) | ~9s |
| Leader integration (E4B) | ~25s |
| **Total** | **~34s** |

VRAM note: E4B + E2B × 3 exceeds 12GB VRAM; Ollama offloads layers to RAM automatically.

## License

MIT
