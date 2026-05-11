# gemma4_tribe/main.py
# CLI entry point for gemma4_tribe

import asyncio
import sys
from tribe import run_tribe

BANNER = """
╔══════════════════════════════════════╗
║          gemma4_tribe v0.1           ║
║  📅 Koyomi (E4B) leads               ║
║  🌕 Mochi  (E2B) — emotion           ║
║  🗓️  Jun    (E2B) — logic+expression  ║
║  🗝️  Uruu   (E2B) — analysis         ║
╚══════════════════════════════════════╝
"""

DEMO_QUESTIONS = [
    "I'm feeling stuck on a project. I know what needs to be done but can't start.",
    "What's the best way to explain a complex system to someone who isn't technical?",
    "I just found out some unexpected good news. How do I process this?",
]


async def interactive_loop():
    print(BANNER)
    print("Type your message, or 'demo' to run a demo question, or 'quit' to exit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("bye")
            break
        if user_input.lower() == "demo":
            import random
            user_input = random.choice(DEMO_QUESTIONS)
            print(f"Demo: {user_input}\n")

        await run_tribe(user_input, verbose=True)
        print()


async def single_run(message: str):
    result = await run_tribe(message, verbose=True)
    # result is now a dict; verbose=True already prints everything


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Direct message from command line
        message = " ".join(sys.argv[1:])
        asyncio.run(single_run(message))
    else:
        # Interactive mode
        asyncio.run(interactive_loop())
