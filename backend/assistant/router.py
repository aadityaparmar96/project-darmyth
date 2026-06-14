# =============================================================
#  Darmyth — backend/assistant/router.py
#  Intent router — handles simple commands locally,
#  only sends complex queries to Groq API.
# =============================================================

import os
import sys
import subprocess
import webbrowser
from datetime import datetime
import psutil

# ── Intent categories ─────────────────────────────────────────
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
        "mute", "mute volume", "silence"
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

    # ── Web URLs ──────────────────────────────────────────────
    "open_url": [
        "open youtube", "open google", "open gmail", "open github",
        "open instagram", "open twitter", "open facebook", "open netflix",
        "go to youtube", "go to google", "open in chrome", "open in browser",
        "open spotify", "open reddit", "open twitch"
    ],

    # ── Web search ────────────────────────────────────────────
    "search_web": [
        "search for", "google", "look up", "search the web", "find online"
    ],

    # ── Stylus control ────────────────────────────────────────
    "stylus_on": [
        "activate stylus", "enable stylus", "start stylus",
        "turn on stylus", "hand control on", "gesture mode",
        "start hand tracking", "enable hand control", "stylus on"
    ],
    "stylus_off": [
        "close stylus", "disable stylus", "stop stylus",
        "turn off stylus", "hand control off", "exit gesture mode",
        "stop hand tracking", "deactivate stylus", "stylus off"
    ],

    # ── Shutdown ──────────────────────────────────────────────
    "shutdown": [
        "goodbye darmyth", "bye darmyth", "shutdown darmyth",
        "exit darmyth", "quit darmyth", "turn off darmyth",
        "sleep darmyth"
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

# ── URL map ───────────────────────────────────────────────────
URL_MAP = {
    "youtube":   "https://youtube.com",
    "google":    "https://google.com",
    "gmail":     "https://gmail.com",
    "github":    "https://github.com",
    "instagram": "https://instagram.com",
    "twitter":   "https://twitter.com",
    "netflix":   "https://netflix.com",
    "facebook":  "https://facebook.com",
    "spotify":   "https://open.spotify.com",
    "reddit":    "https://reddit.com",
    "twitch":    "https://twitch.tv",
}

# ── Volume control ────────────────────────────────────────────
def _change_volume(action: str) -> str:
    try:
        if action == "up":
            script = "$wsh = New-Object -ComObject WScript.Shell; 1..5 | ForEach-Object { $wsh.SendKeys([char]175) }"
        elif action == "down":
            script = "$wsh = New-Object -ComObject WScript.Shell; 1..5 | ForEach-Object { $wsh.SendKeys([char]174) }"
        elif action == "mute":
            script = "$wsh = New-Object -ComObject WScript.Shell; $wsh.SendKeys([char]173)"
        subprocess.run(["powershell", "-Command", script],
                      capture_output=True, timeout=5)
        return {"up": "Volume increased.", "down": "Volume decreased.",
                "mute": "Muted."}[action]
    except Exception as e:
        return f"Volume control failed: {e}"


# ── Intent handlers ───────────────────────────────────────────
def _handle_intent(intent: str, user_input: str) -> str:

    # Time & Date
    if intent == "get_time":
        return f"It's {datetime.now().strftime('%I:%M %p')}."
    if intent == "get_date":
        return f"Today is {datetime.now().strftime('%A, %B %d, %Y')}."

    # System stats
    if intent == "get_ram":
        ram = psutil.virtual_memory()
        used = ram.used / (1024**3)
        total = ram.total / (1024**3)
        return f"RAM: {used:.1f}GB used of {total:.1f}GB ({ram.percent}% full)."
    if intent == "get_cpu":
        return f"CPU usage: {psutil.cpu_percent(interval=1)}%."
    if intent == "get_battery":
        battery = psutil.sensors_battery()
        if battery:
            status = "charging" if battery.power_plugged else "on battery"
            return f"Battery: {battery.percent:.0f}% ({status})."
        return "No battery detected."

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

    # URL opening
    if intent == "open_url":
        text = user_input.lower()
        for site, url in URL_MAP.items():
            if site in text:
                webbrowser.open(url)
                return f"Opening {site.title()}."
        webbrowser.open("https://google.com")
        return "Opening browser."

    # Web search
    if intent == "search_web":
        query = user_input.lower()
        for trigger in INTENT_MAP["search_web"]:
            query = query.replace(trigger, "").strip()
        if query:
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            webbrowser.open(url)
            return f"Searching for '{query}'."
        return "What do you want me to search for?"

    # Stylus control — special signals handled by main.py
    if intent == "stylus_on":
        return "STYLUS_ON"
    if intent == "stylus_off":
        return "STYLUS_OFF"

    # Shutdown — special signal handled by main.py
    if intent == "shutdown":
        return "SHUTDOWN"

    # Darmyth control
    if intent == "clear_memory":
        return "CLEAR_MEMORY"

    if intent == "help":
        return (
            "Here's what I can handle directly:\n"
            "• Time & date — 'what time is it', 'what day is it'\n"
            "• System info — 'cpu usage', 'ram usage', 'battery level'\n"
            "• Volume — 'volume up', 'volume down', 'mute'\n"
            "• Apps — 'open chrome', 'open notepad', 'open calculator'\n"
            "• Websites — 'open youtube', 'open github', 'open spotify'\n"
            "• Search — 'search for Python tutorials'\n"
            "• Stylus — 'activate stylus', 'close stylus'\n"
            "• Memory — 'clear memory'\n"
            "• Shutdown — 'goodbye Darmyth'\n"
            "Anything else goes to my AI brain."
        )

    return None


# ── Main routing function ─────────────────────────────────────
def route(user_input: str) -> dict:
    """
    Route user input to the right handler.
    Returns {"intent": str, "handled": bool, "response": str}
    """
    text = user_input.lower().strip()

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
        "Open youtube",
        "Search for Python tutorials",
        "Activate stylus",
        "Close stylus",
        "Goodbye Darmyth",
        "What is the meaning of life?",
        "Help",
    ]

    for user_input in test_inputs:
        result = route(user_input)
        if result["handled"]:
            print(f"You:     {user_input}")
            print(f"Darmyth: {result['response']}")
        else:
            print(f"You:     {user_input}")
            print(f"Darmyth: [→ sending to Groq]")
        print("-" * 50)