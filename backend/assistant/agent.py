# =============================================================
#  Darmyth — backend/assistant/agent.py
#  Agentic PC control using Groq tool calling
#  Groq decides what action to take, agent executes it
# =============================================================

import os
import json
import subprocess
import webbrowser
import pyautogui
import psutil
from datetime import datetime
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
import yaml

# ── Load config ───────────────────────────────────────────────
BASE_DIR  = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=BASE_DIR / "config" / ".env", override=True)

with open(BASE_DIR / "config" / "settings.yaml") as f:
    SETTINGS = yaml.safe_load(f)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL        = SETTINGS["assistant"]["model"]

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# =============================================================
#  Tool definitions — Groq sees these and picks the right one
# =============================================================
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "open_application",
            "description": "Open any application installed on the PC by name",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Name of the app e.g. 'chrome', 'notepad', 'spotify', 'vscode'"
                    }
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_website",
            "description": "Open any website in the default browser",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full URL or site name e.g. 'youtube.com', 'https://github.com'"
                    },
                    "incognito": {
                        "type": "boolean",
                        "description": "Open in incognito/private mode"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search Google for any query",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "control_volume",
            "description": "Control system volume",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["up", "down", "mute", "unmute"],
                        "description": "Volume action"
                    },
                    "amount": {
                        "type": "integer",
                        "description": "Number of steps to change volume (1-10)",
                        "default": 5
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "Get current system information like RAM, CPU, battery, time, date",
            "parameters": {
                "type": "object",
                "properties": {
                    "info_type": {
                        "type": "string",
                        "enum": ["all", "ram", "cpu", "battery", "time", "date", "storage"],
                        "description": "Type of info to retrieve"
                    }
                },
                "required": ["info_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text at the current cursor position",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to type"
                    }
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "press_key",
            "description": "Press a keyboard shortcut or key combination",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "string",
                        "description": "Key or combo e.g. 'ctrl+c', 'alt+tab', 'enter', 'win+d'"
                    }
                },
                "required": ["keys"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Take a screenshot of the current screen",
            "parameters": {
                "type": "object",
                "properties": {
                    "save_path": {
                        "type": "string",
                        "description": "Optional path to save the screenshot"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_terminal_command",
            "description": "Run a safe terminal/shell command on Windows",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command to run e.g. 'dir', 'ipconfig', 'echo hello'"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "close_application",
            "description": "Close a running application by name",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Name of the app to close e.g. 'chrome', 'notepad'"
                    }
                },
                "required": ["app_name"]
            }
        }
    },
]

# =============================================================
#  Tool executor — actually runs the actions on the PC
# =============================================================

# App name → executable mapping
APP_MAP = {
    "chrome":      "start chrome",
    "google chrome": "start chrome",
    "firefox":     "start firefox",
    "edge":        "start msedge",
    "notepad":     "notepad",
    "calculator":  "calc",
    "calc":        "calc",
    "explorer":    "explorer",
    "file explorer": "explorer",
    "paint":       "mspaint",
    "word":        "start winword",
    "excel":       "start excel",
    "powerpoint":  "start powerpnt",
    "vscode":      "code",
    "vs code":     "code",
    "spotify":     "start spotify",
    "discord":     "start discord",
    "terminal":    "start wt",
    "powershell":  "start powershell",
    "cmd":         "start cmd",
    "task manager": "taskmgr",
    "settings":    "start ms-settings:",
    "camera":      "start microsoft.windows.camera:",
}

def _execute_tool(tool_name: str, args: dict) -> str:
    """Execute a tool and return a result string."""

    # ── Open application ──────────────────────────────────────
    if tool_name == "open_application":
        app = args.get("app_name", "").lower().strip()
        cmd = APP_MAP.get(app)
        if cmd:
            subprocess.Popen(cmd, shell=True)
            return f"Opened {args['app_name']}."
        else:
            # Try directly
            try:
                subprocess.Popen(app, shell=True)
                return f"Attempted to open {app}."
            except Exception as e:
                return f"Could not open {app}: {e}"

    # ── Open website ──────────────────────────────────────────
    elif tool_name == "open_website":
        url       = args.get("url", "")
        incognito = args.get("incognito", False)

        if not url.startswith("http"):
            url = "https://" + url

        if incognito:
            subprocess.Popen(f"start chrome --incognito {url}", shell=True)
            return f"Opened {url} in incognito."
        else:
            webbrowser.open(url)
            return f"Opened {url}."

    # ── Search web ────────────────────────────────────────────
    elif tool_name == "search_web":
        query = args.get("query", "")
        url   = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        webbrowser.open(url)
        return f"Searching for '{query}'."

    # ── Volume control ────────────────────────────────────────
    elif tool_name == "control_volume":
        action = args.get("action", "up")
        amount = args.get("amount", 5)
        try:
            script_map = {
                "up":     f"$wsh = New-Object -ComObject WScript.Shell; 1..{amount} | ForEach-Object {{ $wsh.SendKeys([char]175) }}",
                "down":   f"$wsh = New-Object -ComObject WScript.Shell; 1..{amount} | ForEach-Object {{ $wsh.SendKeys([char]174) }}",
                "mute":   "$wsh = New-Object -ComObject WScript.Shell; $wsh.SendKeys([char]173)",
                "unmute": "$wsh = New-Object -ComObject WScript.Shell; $wsh.SendKeys([char]173)",
            }
            subprocess.run(["powershell", "-Command", script_map[action]],
                          capture_output=True, timeout=5)
            return f"Volume {action}."
        except Exception as e:
            return f"Volume control failed: {e}"

    # ── System info ───────────────────────────────────────────
    elif tool_name == "get_system_info":
        info_type = args.get("info_type", "all")
        results   = []

        if info_type in ("all", "time"):
            results.append(f"Time: {datetime.now().strftime('%I:%M %p')}")
        if info_type in ("all", "date"):
            results.append(f"Date: {datetime.now().strftime('%A, %B %d, %Y')}")
        if info_type in ("all", "ram"):
            ram = psutil.virtual_memory()
            results.append(f"RAM: {ram.used/1e9:.1f}GB / {ram.total/1e9:.1f}GB ({ram.percent}%)")
        if info_type in ("all", "cpu"):
            results.append(f"CPU: {psutil.cpu_percent(interval=1)}%")
        if info_type in ("all", "battery"):
            bat = psutil.sensors_battery()
            if bat:
                status = "charging" if bat.power_plugged else "on battery"
                results.append(f"Battery: {bat.percent:.0f}% ({status})")
        if info_type in ("all", "storage"):
            disk = psutil.disk_usage('/')
            results.append(f"Storage: {disk.used/1e9:.1f}GB used / {disk.total/1e9:.1f}GB total")

        return " | ".join(results) if results else "Could not get system info."

    # ── Type text ─────────────────────────────────────────────
    elif tool_name == "type_text":
        text = args.get("text", "")
        import time
        time.sleep(0.5)  # give focus time to settle
        pyautogui.typewrite(text, interval=0.05)
        return f"Typed: {text[:50]}"

    # ── Press key ─────────────────────────────────────────────
    elif tool_name == "press_key":
        keys = args.get("keys", "")
        pyautogui.hotkey(*keys.split("+"))
        return f"Pressed: {keys}"

    # ── Screenshot ────────────────────────────────────────────
    elif tool_name == "take_screenshot":
        save_path = args.get("save_path") or f"screenshot_{int(datetime.now().timestamp())}.png"
        img = pyautogui.screenshot()
        img.save(save_path)
        return f"Screenshot saved to {save_path}."

    # ── Run command ───────────────────────────────────────────
    elif tool_name == "run_terminal_command":
        # Safety — block dangerous commands
        command = args.get("command", "")
        blocked = ["rm", "del", "format", "shutdown", "rd /s", "rmdir"]
        if any(b in command.lower() for b in blocked):
            return f"Blocked dangerous command: {command}"
        try:
            result = subprocess.run(
                command, shell=True,
                capture_output=True, text=True, timeout=10
            )
            output = result.stdout.strip() or result.stderr.strip() or "Command executed."
            return output[:300]
        except Exception as e:
            return f"Command failed: {e}"

    # ── Close application ─────────────────────────────────────
    elif tool_name == "close_application":
        app = args.get("app_name", "").lower()
        process_map = {
            "chrome": "chrome.exe",
            "firefox": "firefox.exe",
            "notepad": "notepad.exe",
            "spotify": "Spotify.exe",
            "discord": "Discord.exe",
            "edge": "msedge.exe",
            "obsidian" : "obsidian.exe",
        }
        proc_name = process_map.get(app, app + ".exe")
        killed = False
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] and proc_name.lower() in proc.info['name'].lower():
                proc.kill()
                killed = True
        return f"Closed {app}." if killed else f"Could not find {app} running."

    return f"Unknown tool: {tool_name}"


# =============================================================
#  Agent — sends to Groq with tools, executes results
# =============================================================
SYSTEM_PROMPT = """You are Darmyth, an AI desktop assistant with full PC control.
When the user asks you to do something on their computer, use the available tools.
Be concise in your responses. After executing a tool, briefly confirm what you did.
For questions that don't require PC actions, just answer directly without using tools.
Never ask for confirmation before using tools — just do it."""

def run_agent(user_message: str, conversation_history: list = None) -> str:
    """
    Send message to Groq with tool definitions.
    Groq decides which tool to call, agent executes it.

    Returns:
        Final response string
    """
    history = conversation_history or []

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
        {"role": "user", "content": user_message}
    ]

    print(f"[agent] Processing: '{user_message[:60]}'")

    try:
        # First call — Groq may return tool calls
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=1024,
            temperature=0.3,
        )

        msg = response.choices[0].message

        # ── No tool call — just a text response ───────────────
        if not msg.tool_calls:
            print("[agent] No tool needed — text response.")
            return msg.content.strip()

        # ── Tool calls — execute each one ─────────────────────
        tool_results = []
        for tc in msg.tool_calls:
            tool_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except Exception:
                args = {}

            print(f"[agent] Calling tool: {tool_name}({args})")
            result = _execute_tool(tool_name, args)
            print(f"[agent] Tool result: {result}")

            tool_results.append({
                "tool_call_id": tc.id,
                "role":         "tool",
                "name":         tool_name,
                "content":      result,
            })

        # ── Second call — Groq summarises what happened ───────
        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": msg.tool_calls})
        messages.extend(tool_results)

        final = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=256,
            temperature=0.3,
        )

        return final.choices[0].message.content.strip()

    except Exception as e:
        print(f"[agent] Error: {e}")
        return f"I ran into an issue: {e}"


# =============================================================
#  Quick test
# =============================================================
if __name__ == "__main__":
    print("Testing Darmyth Agent\n")
    print("Type commands to test PC control.")
    print("Try: 'open youtube', 'what time is it', 'search for python tutorials'")
    print("Type 'quit' to exit\n")

    history = []
    while True:
        user = input("You: ").strip()
        if user.lower() == "quit":
            break
        if not user:
            continue

        response = run_agent(user, history)
        print(f"Darmyth: {response}\n")

        history.append({"role": "user", "content": user})
        history.append({"role": "assistant", "content": response})

        # Keep last 6 turns
        if len(history) > 12:
            history = history[-12:]