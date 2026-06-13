# =============================================================
#  Darmyth — backend/assistant/computer_agent.py
#  Screenshot + Gemini Vision PC control
#  DPI scaling fix: logical coords × 1.25 = physical coords
#  Gemini sees 1536x864, PyAutoGUI clicks on 1920x1080
# =============================================================

import os
import base64
import json
import time
import threading
import queue
import pyautogui
import subprocess
import webbrowser
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

# ── Config ────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=BASE_DIR / "config" / ".env", override=True)

GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")
SCREENSHOT_PATH = str(BASE_DIR / "data" / "agent_screen.png")

pyautogui.FAILSAFE = True
pyautogui.PAUSE    = 0.1

# ── DPI scaling ───────────────────────────────────────────────
# Windows display scaling = 125%
# Gemini sees logical pixels (1536x864)
# PyAutoGUI needs physical pixels (1920x1080)
SCALE_FACTOR = 1.25

PHYSICAL_W, PHYSICAL_H = pyautogui.size()                    # 1920x1080
LOGICAL_W  = int(PHYSICAL_W / SCALE_FACTOR)                  # 1536
LOGICAL_H  = int(PHYSICAL_H / SCALE_FACTOR)                  # 864

def scale(x, y) -> tuple:
    """Convert Gemini logical coords → PyAutoGUI physical coords."""
    return int(float(x) * SCALE_FACTOR), int(float(y) * SCALE_FACTOR)

# ── Gemini client ─────────────────────────────────────────────
gemini_client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
) if GEMINI_API_KEY else None

FLASH_MODEL = "models/gemini-2.5-flash"

# ── Rate limit handling ───────────────────────────────────────
RATE_LIMIT_WAIT = 65   # seconds to wait on 429

# =============================================================
#  Screenshot
# =============================================================
def screenshot() -> str:
    """Take screenshot at logical resolution for Gemini."""
    img = pyautogui.screenshot()
    # Resize to logical resolution so Gemini coords match 1:1
    from PIL import Image
    logical = img.resize((LOGICAL_W, LOGICAL_H), Image.LANCZOS)
    logical.save(SCREENSHOT_PATH)
    return SCREENSHOT_PATH

def to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

# =============================================================
#  Gemini vision
# =============================================================
def ask_gemini(question: str, img_path: str = None,
               retries: int = 3) -> str:
    if not gemini_client:
        return "ERROR: GEMINI_API_KEY not configured."

    if not img_path:
        img_path = screenshot()

    img_b64 = to_base64(img_path)

    for attempt in range(retries):
        try:
            response = gemini_client.chat.completions.create(
                model=FLASH_MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                        {"type": "text", "text": question}
                    ]
                }],
                max_tokens=1024,
                temperature=0.1,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            err = str(e)
            if "429" in err:
                wait = RATE_LIMIT_WAIT * (attempt + 1)
                print(f"[agent] Rate limit — waiting {wait}s...")
                time.sleep(wait)
            else:
                return f"ERROR: {e}"

    return "ERROR: Max retries exceeded"

def parse_json(text: str):
    """Parse JSON from Gemini response robustly."""
    if not text or text.startswith("ERROR"):
        return None
    try:
        clean = text.strip()
        # Strip markdown code blocks
        if "```" in clean:
            parts = clean.split("```")
            for p in parts:
                p = p.strip().lstrip("json").strip()
                if p.startswith("{") or p.startswith("["):
                    clean = p
                    break
        # Find JSON object even if surrounded by text
        start = clean.find("{")
        end   = clean.rfind("}") + 1
        if start != -1 and end > start:
            clean = clean[start:end]
        return json.loads(clean)
    except Exception:
        return None

# =============================================================
#  Action executor
# =============================================================
def execute_action(action: dict) -> tuple:
    """Execute action. Returns (success, message)."""
    act  = action.get("action", "").lower()
    desc = action.get("description", act)

    try:
        if act == "click":
            x, y   = action.get("x"), action.get("y")
            px, py = scale(x, y)
            pyautogui.click(px, py)
            return True, f"Clicked ({x},{y}) → physical ({px},{py}) — {desc}"

        elif act == "double_click":
            x, y   = action.get("x"), action.get("y")
            px, py = scale(x, y)
            pyautogui.doubleClick(px, py)
            return True, f"Double clicked ({x},{y}) → ({px},{py})"

        elif act == "right_click":
            x, y   = action.get("x"), action.get("y")
            px, py = scale(x, y)
            pyautogui.rightClick(px, py)
            return True, f"Right clicked ({x},{y}) → ({px},{py})"

        elif act == "type":
            text = action.get("text", "")
            pyautogui.typewrite(text, interval=0.04)
            return True, f"Typed: {text[:60]}"

        elif act == "type_paste":
            # For special chars or long text — use clipboard
            text = action.get("text", "")
            import pyperclip
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
            return True, f"Pasted: {text[:60]}"

        elif act == "key":
            keys     = action.get("keys", "")
            key_list = [k.strip() for k in keys.split("+")]
            pyautogui.hotkey(*key_list)
            return True, f"Pressed: {keys}"

        elif act == "scroll":
            x      = action.get("x", LOGICAL_W // 2)
            y      = action.get("y", LOGICAL_H // 2)
            amount = action.get("amount", 3)
            px, py = scale(x, y)
            pyautogui.scroll(amount, x=px, y=py)
            return True, f"Scrolled {amount} at ({x},{y})"

        elif act == "move":
            x, y   = action.get("x"), action.get("y")
            px, py = scale(x, y)
            pyautogui.moveTo(px, py, duration=0.2)
            return True, f"Moved to ({x},{y}) → ({px},{py})"

        elif act == "drag":
            x1, y1 = action.get("x1"), action.get("y1")
            x2, y2 = action.get("x2"), action.get("y2")
            px1, py1 = scale(x1, y1)
            px2, py2 = scale(x2, y2)
            pyautogui.drag(px1, py1, px2-px1, py2-py1,
                          duration=0.5, button='left')
            return True, f"Dragged ({x1},{y1})→({x2},{y2})"

        elif act == "wait":
            secs = float(action.get("seconds", 1))
            time.sleep(secs)
            return True, f"Waited {secs}s"

        elif act == "open_url":
            url = action.get("url", "")
            if not url.startswith("http"):
                url = "https://" + url
            webbrowser.open(url)
            time.sleep(2)
            return True, f"Opened {url}"

        elif act == "run_command":
            cmd     = action.get("command", "")
            blocked = ["rm -rf", "del /f /s", "format c:", "shutdown /s"]
            if any(b in cmd.lower() for b in blocked):
                return False, f"Blocked: {cmd}"
            result = subprocess.run(
                cmd, shell=True, capture_output=True,
                text=True, timeout=15
            )
            out = (result.stdout + result.stderr).strip()[:200]
            return True, f"Ran: {cmd}\n{out}"

        elif act == "done":
            return True, action.get("message", "Task complete.")

        elif act == "fail":
            return False, action.get("message", "Task failed.")

        else:
            return False, f"Unknown action: {act}"

    except Exception as e:
        return False, f"Action error: {e}"

# =============================================================
#  Step prompt — Gemini decides next action
# =============================================================
STEP_PROMPT = """You are controlling a Windows 11 PC.
Screen is {w}x{h} logical pixels (already scaled for you — use these coordinates directly).
Physical resolution is 1920x1080 but you don't need to worry about that.

Task: {task}
Steps done so far: {history}
Attempt: {attempt}/{max_steps}

Look at the screenshot. What is the SINGLE NEXT ACTION to complete this task?

Return ONLY a JSON object. Examples:

Click something:
{{"action": "click", "x": 760, "y": 540, "description": "clicking the search bar"}}

Type text (simple):
{{"action": "type", "text": "Obsidian"}}

Type text with special chars or long content:
{{"action": "type_paste", "text": "Hello World!"}}

Press a key or combo:
{{"action": "key", "keys": "enter"}}
{{"action": "key", "keys": "ctrl+s"}}
{{"action": "key", "keys": "win+s"}}

Open a URL directly:
{{"action": "open_url", "url": "https://youtube.com"}}

Run a shell command:
{{"action": "run_command", "command": "start notepad"}}
{{"action": "run_command", "command": "start obsidian"}}

Wait for app to load:
{{"action": "wait", "seconds": 2}}

Task is fully complete:
{{"action": "done", "message": "what was accomplished"}}

Task is impossible:
{{"action": "fail", "message": "why it failed"}}

RULES:
- Return ONLY the JSON, nothing else
- Coordinates must be within 0-{w} (x) and 0-{h} (y)
- Click the CENTER of elements
- After typing in a search bar, always follow with key enter
- If opening an app, prefer run_command over clicking
- Wait after opening apps before doing more actions
- Be precise — look carefully at where elements actually are
"""

PLAN_PROMPT = """Break this task into simple sequential subtasks.
Task: {task}

Return ONLY a JSON array of subtask strings. Keep each subtask short and clear.
Example: ["open obsidian", "create new note", "type the content", "save the file"]

Max 8 subtasks. Return ONLY the JSON array."""

# =============================================================
#  Subtask runner
# =============================================================
def run_subtask(task: str, callback=None,
                max_steps: int = 20) -> tuple:
    """Run one subtask. Returns (success, message)."""
    log     = lambda m: (print(f"[agent] {m}"),
                        callback(m) if callback else None)
    history = []

    log(f"Subtask: {task}")

    for step in range(1, max_steps + 1):
        img_path = screenshot()

        prompt = STEP_PROMPT.format(
            task=task,
            w=LOGICAL_W,
            h=LOGICAL_H,
            history=json.dumps(history[-4:]) if history else "none yet",
            attempt=step,
            max_steps=max_steps
        )

        raw    = ask_gemini(prompt, img_path=img_path)
        action = parse_json(raw)

        if not action:
            log(f"Step {step}: bad response — {raw[:100]}")
            time.sleep(2)
            continue

        log(f"Step {step}: {action.get('action')} — {action.get('description', '')}")
        success, message = execute_action(action)
        history.append({"step": step, "action": action.get("action"),
                        "result": message[:80]})
        log(f"  ✓ {message}" if success else f"  ✗ {message}")

        if action.get("action") == "done":
            return True, message
        if action.get("action") == "fail":
            return False, message

        time.sleep(0.5)

    return False, f"Exceeded {max_steps} steps"

# =============================================================
#  Main task runner — decomposes + runs subtasks
# =============================================================
def run_task(task: str, callback=None) -> str:
    log = lambda m: (print(f"[computer_agent] {m}"),
                    callback(m) if callback else None)

    log(f"Task: {task}")

    # Decide if complex enough to decompose
    complex_signals = ["then", "and then", "after", "also", "create",
                       "write", "open", "go to", "search", "type"]
    word_count = len(task.split())

    if word_count > 8 or sum(1 for s in complex_signals if s in task.lower()) > 2:
        log("Decomposing into subtasks...")
        img_path = screenshot()
        raw      = ask_gemini(
            PLAN_PROMPT.format(task=task),
            img_path=img_path
        )
        subtasks = parse_json(raw)
        if not isinstance(subtasks, list) or not subtasks:
            log("Could not decompose — running as single task")
            subtasks = [task]
        else:
            log(f"Subtasks: {subtasks}")
    else:
        subtasks = [task]

    results = []
    for i, subtask in enumerate(subtasks):
        log(f"\n[{i+1}/{len(subtasks)}] {subtask}")
        ok, msg = run_subtask(subtask, callback=callback)
        results.append(f"{'✓' if ok else '✗'} {subtask}: {msg}")
        time.sleep(1.5)

    return "\n".join(results)

# =============================================================
#  Background session
# =============================================================
class AgentSession:
    def __init__(self, on_update=None, on_complete=None):
        self.on_update   = on_update   or (lambda m: print(f"[session] {m}"))
        self.on_complete = on_complete or (lambda m: print(f"[session] ✓ {m}"))
        self._queue      = queue.Queue()
        self._running    = False
        self._thread     = None
        self._current    = None

    def add_task(self, task: str):
        self._queue.put(task)
        self.on_update(f"Queued: {task}")
        if not self._running:
            self._start()

    def _start(self):
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _worker(self):
        self._running = True
        while self._running:
            try:
                task = self._queue.get(timeout=2)
                self._current = task
                result = run_task(task, callback=self.on_update)
                self.on_complete(result)
                self._current = None
                self._queue.task_done()
            except queue.Empty:
                if self._queue.empty():
                    self._running = False

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)

    @property
    def is_busy(self) -> bool:
        return self._current is not None

# =============================================================
#  Quick test
# =============================================================
if __name__ == "__main__":
    import sys

    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not in config/.env")
        sys.exit(1)

    print("Darmyth Computer Agent")
    print(f"Screen: {PHYSICAL_W}x{PHYSICAL_H} physical | "
          f"{LOGICAL_W}x{LOGICAL_H} logical (scale {SCALE_FACTOR}x)")
    print("=" * 55)
    print("Move mouse to TOP-LEFT corner to emergency stop.")
    print("Type 'quit' to exit\n")

    session = AgentSession(
        on_update  = lambda m: print(f"  {m}"),
        on_complete= lambda m: print(f"\nDone:\n{m}\n\nYou: ", end="", flush=True)
    )

    print("You: ", end="", flush=True)
    while True:
        try:
            task = input().strip()
        except (EOFError, KeyboardInterrupt):
            break
        if task.lower() == "quit":
            break
        if not task:
            print("You: ", end="", flush=True)
            continue

        session.add_task(task)
        while session.is_busy:
            time.sleep(0.3)

    session.stop()
    print("Goodbye.")