# =============================================================
#  Darmyth — backend/assistant/router.py
#  Intent router — handles simple commands locally,
#  only sends complex queries to Groq API.
#  
#  Flow: user input → router → local action OR brain.py
# =============================================================

import os
import sys
import subprocess
import webbrowser
from datetime import datetime
import psutil

# ── Intent categories ─────────────────────────────────────────
# Each intent has a list of trigger keywords/phrases
# Order matters — more specific phrases first

INTENT_MAP = {
    # ── Time & Date ───────────────────────────────────────────
    "get_time": [
        "what time", "current time", "what's the time", "tell me the time"
    ],
    "get_date": [
        "what date", "today's date", "what day is it", "current date"
    ],

    # ── System stats ──────────────────────────────────────────
    "get_ram": [
        "ram usage", "memory usage", "how much ram", "check memory",
        "memory stats"
    ],
    "get_cpu": [
        "cpu usage", "processor usage", "how much cpu", "check cpu"
    ],
    "get_battery": [
        "battery", "how much battery", "battery level", "charge level"
    ],

    # ── Volume control ────────────────────────────────────────
    "volume_up": [
        "volume up", "increase volume", "louder", "turn up"
    ],
    "volume_down": [
        "volume down", "decrease volume", "quieter", "turn down", "lower volume"
    ],
    "volume_mute": [
        "mute", "mute volume", "silence", "shut up"
    ],

    # ── App launching ─────────────────────────────────────────
    "open_browser": [
        "open browser", "open chrome", "open firefox", "open edge",
        "launch browser", "open internet"
    ],
    "open_notepad": [
        "open notepad", "open notes", "open text editor", "notepad"
    ],
    "open_explorer": [
        "open explorer", "open files", "file explorer", "open folder"
    ],
    "open_calculator": [
        "open calculator", "calculator", "calc"
    ],
    "open_terminal": [
        "open terminal", "open powershell", "open command prompt",
        "open cmd", "terminal"
    ],

    # ── Web search ────────────────────────────────────────────
    "search_web": [
        "search for", "google", "look up", "search the web", "find online"
    ],

    # ── Darmyth control ───────────────────────────────────────
    "clear_memory": [
        "clear memory", "forget everything", "reset conversation",
        "start over", "clear chat"
    ],
    "help": [
        "what can you do", "help", "commands", "what are your commands",
        "show commands"
    ],
}

# ── Windows app paths ─────────────────────────────────────────
APP_PATHS = {
    "open_browser":    "start msedge",
    "open_notepad":    "notepad",
    "open_explorer":   "explorer",
    "open_calculator": "calc",
    "open_terminal":   "start powershell",
}

# ── Volume control (Windows) ──────────────────────────────────
def _change_volume(action: str) -> str:
    """Control system volume using PowerShell."""
    try:
        if action == "up":
            # Press volume up key 5 times
            script = """
            $wsh = New-Object -ComObject WScript.Shell
            1..5 | ForEach-Object { $wsh.SendKeys([char]175) }
            """
        elif action == "down":
            script = """
            $wsh = New-Object -ComObject WScript.Shell
            1..5 | ForEach-Object { $wsh.SendKeys([char]174) }
            """
        elif action == "mute":
            script = """
            $wsh = New-Object -ComObject WScript.Shell
            $wsh.SendKeys([char]173)
            """
        subprocess.run(["powershell", "-Command", script],
                      capture_output=True, timeout=5)
        return {"up": "Volume increased.", "down": "Volume decreased.",
                "mute": "Muted."}[action]
    except Exception as e:
        return f"Volume control failed: {e}"


# ── Intent handlers ───────────────────────────────────────────
def _handle_intent(intent: str, user_input: str) -> str:
    """Execute the action for a detected intent."""

    # Time & Date
    if intent == "get_time":
        return f"It's {datetime.now().strftime('%I:%M %p')}."

    if intent == "get_date":
        return f"Today is {datetime.now().strftime('%A, %B %d, %Y')}."

    # System stats
    if intent == "get_ram":
        ram = psutil.virtual_memory()
        used  = ram.used  / (1024**3)
        total = ram.total / (1024**3)
        pct   = ram.percent
        return f"RAM: {used:.1f}GB used of {total:.1f}GB ({pct}% full)."

    if intent == "get_cpu":
        cpu = psutil.cpu_percent(interval=1)
        return f"CPU usage: {cpu}%."

    if intent == "get_battery":
        battery = psutil.sensors_battery()
        if battery:
            status = "charging" if battery.power_plugged else "on battery"
            return f"Battery: {battery.percent:.0f}% ({status})."
        return "No battery detected — probably a desktop."

    # Volume
    if intent == "volume_up":
        return _change_volume("up")
    if intent == "volume_down":
        return _change_volume("down")
    if intent == "volume_mute":
        return _change_volume("mute")

    # App launching
    if intent in APP_PATHS:
        try:
            subprocess.Popen(APP_PATHS[intent], shell=True)
            app_name = intent.replace("open_", "").replace("_", " ").title()
            return f"Opening {app_name}."
        except Exception as e:
            return f"Couldn't open app: {e}"

    # Web search
    if intent == "search_web":
        # Extract search query — remove trigger words
        query = user_input.lower()
        for trigger in INTENT_MAP["search_web"]:
            query = query.replace(trigger, "").strip()
        if query:
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            webbrowser.open(url)
            return f"Searching for '{query}'."
        return "What do you want me to search for?"

    # Darmyth control
    if intent == "clear_memory":
        return "CLEAR_MEMORY"  # Special signal — brain.py handles this

    if intent == "help":
        return (
            "Here's what I can handle directly:\n"
            "• Time & date — 'what time is it', 'what day is it'\n"
            "• System info — 'cpu usage', 'ram usage', 'battery level'\n"
            "• Volume — 'volume up', 'volume down', 'mute'\n"
            "• Apps — 'open chrome', 'open notepad', 'open calculator'\n"
            "• Search — 'search for Python tutorials'\n"
            "• Memory — 'clear memory'\n"
            "Anything else goes to my AI brain."
        )

    return None  # No handler found — send to brain


# ── Main routing function ─────────────────────────────────────
def route(user_input: str) -> dict:
    """
    Route user input to the right handler.

    Returns a dict:
        {
            "intent":   str,   # detected intent or "llm"
            "handled":  bool,  # True = local, False = send to brain.py
            "response": str    # response if handled locally, else None
        }
    """
    text = user_input.lower().strip()

    # Check each intent
    for intent, triggers in INTENT_MAP.items():
        for trigger in triggers:
            if trigger in text:
                response = _handle_intent(intent, user_input)
                if response is not None:
                    print(f"[router] Intent: {intent} → handled locally")
                    return {
                        "intent":   intent,
                        "handled":  True,
                        "response": response
                    }

    # Nothing matched — send to Groq
    print(f"[router] No intent matched → sending to brain")
    return {
        "intent":   "llm",
        "handled":  False,
        "response": None
    }


# ── Quick test ────────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing Darmyth router...\n")

    test_inputs = [
        "What time is it?",
        "Check my RAM usage",
        "Volume up please",
        "Open calculator",
        "Search for Python tutorials",
        "What is the meaning of life?",    # → should go to LLM
        "Explain quantum computing",        # → should go to LLM
        "What's the battery level?",
        "Clear memory",
        "help",
    ]

    for user_input in test_inputs:
        result = route(user_input)
        if result["handled"]:
            print(f"You:     {user_input}")
            print(f"Darmyth: {result['response']}")
        else:
            print(f"You:     {user_input}")
            print(f"Darmyth: [→ sending to Groq API]")
        print("-" * 50)
