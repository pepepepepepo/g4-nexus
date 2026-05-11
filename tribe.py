# gemma4_tribe/tribe.py
# Core parallel processing engine
# E4B (Koyomi) leads. E2B x3 (Mochi, Jun, Uruu) work in parallel.

import asyncio
import aiohttp
import json
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from personas import KOYOMI_SYSTEM, MOCHI_SYSTEM, JUN_SYSTEM, URUU_SYSTEM


def _extract_response(message: dict) -> str:
    """Extract model response. With think:false, content should be clean already."""
    content = message.get("content", "")
    # Strip any <think>...</think> that slipped through
    clean = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    return clean if clean else content.strip()

# ─── Memory paths ─────────────────────────────────────────
MEMORY_DIR = Path(__file__).parent / "memory"
SESSIONS_DIR = Path(__file__).parent / "sessions"

MEMORY_DIR.mkdir(exist_ok=True)
SESSIONS_DIR.mkdir(exist_ok=True)

PERSONA_MEMORY_FILES = {
    "koyomi": MEMORY_DIR / "koyomi.json",
    "mochi":  MEMORY_DIR / "mochi.json",
    "jun":    MEMORY_DIR / "jun.json",
    "uruu":   MEMORY_DIR / "uruu.json",
}


def _load_memory(name: str) -> dict:
    path = PERSONA_MEMORY_FILES[name]
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"name": name, "observations": [], "to_check": []}


def _save_memory(name: str, data: dict) -> None:
    path = PERSONA_MEMORY_FILES[name]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _build_memory_note(name: str) -> str:
    """Inject last 3 observations into system prompt context."""
    mem = _load_memory(name)
    obs = mem.get("observations", [])[-3:]
    if not obs:
        return ""
    lines = "\n".join(f"- {o}" for o in obs)
    return f"\n\n[Your recent memory]\n{lines}"


def _save_session(result: dict) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SESSIONS_DIR / f"{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return path

OLLAMA_URL = "http://localhost:11434/api/chat"

WORKER_MODEL = "gemma4:e2b"
LEADER_MODEL = "gemma4:e4b"

# Token budgets per role
WORKER_OPTIONS = {
    "num_ctx": 4096,
    "num_predict": 1800,
    "temperature": 1.0,
    "top_p": 0.95,
    "top_k": 64,
}

LEADER_OPTIONS = {
    "num_ctx": 8192,
    "num_predict": 2048,
    "temperature": 1.0,
    "top_p": 0.95,
    "top_k": 64,
}

# ─── Language toggle ──────────────────────────────────────
# True  = respond in Japanese (personal use)
# False = respond in English  (article / external)
RESPOND_IN_JAPANESE = False

@dataclass
class WorkerResult:
    name: str
    emoji: str
    content: str
    elapsed: float
    error: str | None = None


async def call_ollama(
    session: aiohttp.ClientSession,
    model: str,
    system: str,
    user_message: str,
    options: dict,
) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        "stream": False,
        "think": False,   # disable thinking tokens for Gemma 4 / DeepSeek-R1 style models
        "options": options,
    }
    async with session.post(OLLAMA_URL, json=payload) as resp:
        resp.raise_for_status()
        data = await resp.json()
        return _extract_response(data["message"])


async def ask_worker(
    session: aiohttp.ClientSession,
    name: str,
    emoji: str,
    system: str,
    user_message: str,
) -> WorkerResult:
    # Inject personal memory into system prompt
    memory_note = _build_memory_note(name.lower())
    enriched_system = system + memory_note

    t0 = time.perf_counter()
    try:
        content = await call_ollama(
            session, WORKER_MODEL, enriched_system, user_message, WORKER_OPTIONS
        )
        return WorkerResult(
            name=name,
            emoji=emoji,
            content=content,
            elapsed=time.perf_counter() - t0,
        )
    except Exception as e:
        return WorkerResult(
            name=name,
            emoji=emoji,
            content="",
            elapsed=time.perf_counter() - t0,
            error=str(e),
        )


async def ask_leader(
    session: aiohttp.ClientSession,
    user_message: str,
    worker_results: list[WorkerResult],
) -> str:
    # Build integration context for Koyomi
    reports = "\n\n".join(
        f"--- {r.emoji} {r.name} ({r.elapsed:.1f}s) ---\n{r.content}"
        if not r.error
        else f"--- {r.emoji} {r.name} --- ERROR: {r.error}"
        for r in worker_results
    )

    integration_prompt = (
        f"User message: {user_message}\n\n"
        f"Worker reports:\n{reports}\n\n"
        "Now integrate and respond."
    )

    return await call_ollama(
        session, LEADER_MODEL, KOYOMI_SYSTEM, integration_prompt, LEADER_OPTIONS
    )


async def run_tribe(user_message: str, verbose: bool = True) -> dict:
    """
    Main entry point.
    Runs Mochi + Jun + Uruu in parallel (E2B x3),
    then passes all results to Koyomi (E4B) for integration.
    Returns a dict with all results (for API and session saving).
    """
    async with aiohttp.ClientSession() as session:
        if verbose:
            print(f"\n🌕 望 / 🗓️ 旬 / 🗝️ 閏 — parallel workers starting...\n")

        t_start = time.perf_counter()

        # Wrap message with language instruction if enabled
        msg = ("日本語で回答してください。\n\n" + user_message) if RESPOND_IN_JAPANESE else user_message

        # Parallel E2B workers
        worker_results: list[WorkerResult] = await asyncio.gather(
            ask_worker(session, "Mochi", "🌕", MOCHI_SYSTEM, msg),
            ask_worker(session, "Jun",   "🗓️", JUN_SYSTEM,   msg),
            ask_worker(session, "Uruu",  "🗝️", URUU_SYSTEM,  msg),
        )

        t_workers = time.perf_counter() - t_start

        if verbose:
            for r in worker_results:
                status = f"✅ {r.elapsed:.1f}s" if not r.error else f"❌ {r.error}"
                print(f"  {r.emoji} {r.name}: {status}")
                if not r.error:
                    print(f"     {r.content[:120].strip()}...")
            print(f"\n  Workers done in {t_workers:.1f}s total\n")
            print(f"📅 暦 — integrating...\n")

        # E4B leader integration
        final = await ask_leader(session, msg, worker_results)

        t_total = time.perf_counter() - t_start

        if verbose:
            print(f"  ✅ Koyomi done ({t_total:.1f}s total)\n")
            print("=" * 60)
            print(final)
            print("=" * 60)

        # ── Build result dict ──────────────────────────────────
        result = {
            "timestamp": datetime.now().isoformat(),
            "user_message": user_message,
            "workers": [
                {
                    "name": r.name,
                    "emoji": r.emoji,
                    "content": r.content,
                    "elapsed": round(r.elapsed, 2),
                    "error": r.error,
                }
                for r in worker_results
            ],
            "koyomi": final,
            "total_elapsed": round(t_total, 2),
        }

        # ── Save session log ───────────────────────────────────
        session_path = _save_session(result)
        if verbose:
            print(f"  💾 Session saved: {session_path.name}\n")

        # ── Update worker memories ─────────────────────────────
        _update_worker_memory("mochi", user_message, worker_results[0].content)
        _update_worker_memory("jun",   user_message, worker_results[1].content)
        _update_worker_memory("uruu",  user_message, worker_results[2].content)
        _update_koyomi_memory(user_message, final)

        return result


def _update_worker_memory(name: str, question: str, response: str) -> None:
    if not response:
        return
    mem = _load_memory(name)
    # Keep last 20 observations
    short_q = question[:60].replace("\n", " ")
    short_r = response[:80].replace("\n", " ")
    mem["observations"].append(f"Q: {short_q} → {short_r}")
    mem["observations"] = mem["observations"][-20:]
    _save_memory(name, mem)


def _update_koyomi_memory(question: str, final: str) -> None:
    if not final:
        return
    mem = _load_memory("koyomi")
    short_q = question[:60].replace("\n", " ")
    short_f = final[:100].replace("\n", " ")
    mem["observations"].append(f"Q: {short_q} → {short_f}")
    mem["observations"] = mem["observations"][-20:]
    # Extract to_check if Koyomi mentioned one
    if "to_check" not in mem:
        mem["to_check"] = []
    _save_memory("koyomi", mem)
