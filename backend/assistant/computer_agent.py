# =============================================================
#  Darmyth — backend/assistant/computer_agent.py
#  Full computer use agent — no hardcoding
#  Gemini Flash sees screen → plans action → executes → verifies
#  Supports long tasks, subtask decomposition, retry logic
#  Runs in background thread — non-blocking
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

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SCREENSHOT_PATH = str(BASE_DIR / "data" / "agent_screen.png")

pyautogui.FAILSAFE = True
pyautogui.PAUSE    = 0.1

SCREEN_W, SCREEN_H = pyautogui.size()

# ── Gemini clients ────────────────────────────────────────────
flash_client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
) if GEMINI_API_KEY else None

# Gemini Pro for complex planning (50 req/day — used sparingly)
pro_client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
) if GEMINI_API_KEY else None

FLASH_MODEL = "gemini-1.5-flash"
PRO_MODEL   = "gemini-1.5-pro"


# =============================================================
#  Screenshot
# =============================================================
def screenshot() -> str:
    """Take screenshot, save, return path."""
    img = pyautogui.screenshot()
    img.save(SCREENSHOT_PATH)
    return SCREENSHOT_PATH


def to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


# =============================================================
#  Gemini vision calls
# =============================================================
def ask_gemini(question: str, use_pro: bool = False,
               img_path: str = None) -> str:
    """
    Ask Gemini about the current screen.
    use_pro=True for complex planning, Flash for everything else.
    """
    client = pro_client if use_pro else flash_client
    model  = PRO_MODEL  if use_pro else FLASH_MODEL

    if not client:
        return "ERROR: GEMINI_API_KEY not configured."

    if not img_path:
        img_path = screenshot()

    img_b64 = to_base64(img_path)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_b64}"}
                    },
                    {"type": "text", "text": question}
                ]
            }],
            max_tokens=2048,
            temperature=0.1,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"ERROR: {e}"


def parse_json(text: str) -> dict | list | None:
    """Safely parse JSON from Gemini response."""
    try:
        clean = text.strip()
        if "```" in clean:
            parts = clean.split("```")
            for p in parts:
                p = p.strip().lstrip("json").strip()
                if p.startswith("{") or p.startswith("["):
                    clean = p
                    break
        return json.loads(clean)
    except Exception:
        return None


# =============================================================
#  Action executor — all possible actions
# =============================================================
def execute_action(action: dict) -> tuple[bool, str]:
    """
    Execute a single action dict.
    Returns (success, message).
    """
    act  = action.get("action", "").lower()
    desc = action.get("description", act)

    try:
        # ── Click ─────────────────────────────────────────────
        if act == "click":
            x, y = action.get("x"), action.get("y")
            if x is None or y is None:
                return False, "No coordinates provided for click"
            pyautogui.click(int(x), int(y))
            return True, f"Clicked at ({x}, {y}) — {desc}"

        # ── Double click ──────────────────────────────────────
        elif act == "double_click":
            x, y = action.get("x"), action.get("y")
            pyautogui.doubleClick(int(x), int(y))
            return True, f"Double clicked at ({x}, {y})"

        # ── Right click ───────────────────────────────────────
        elif act == "right_click":
            x, y = action.get("x"), action.get("y")
            pyautogui.rightClick(int(x), int(y))
            return True, f"Right clicked at ({x}, {y})"

        # ── Type text ─────────────────────────────────────────
        elif act == "type":
            text = action.get("text", "")
            pyautogui.typewrite(text, interval=0.04)
            return True, f"Typed: {text[:50]}"

        # ── Type with special chars (paste method) ────────────
        elif act == "type_paste":
            text = action.get("text", "")
            import pyperclip
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
            return True, f"Pasted: {text[:50]}"

        # ── Key press ─────────────────────────────────────────
        elif act == "key":
            keys = action.get("keys", "")
            key_list = [k.strip() for k in keys.split("+")]
            pyautogui.hotkey(*key_list)
            return True, f"Pressed: {keys}"

        # ── Scroll ────────────────────────────────────────────
        elif act == "scroll":
            x     = action.get("x", SCREEN_W // 2)
            y     = action.get("y", SCREEN_H // 2)
            amount = action.get("amount", 3)
            pyautogui.scroll(amount, x=int(x), y=int(y))
            return True, f"Scrolled {amount} at ({x}, {y})"

        # ── Move mouse ────────────────────────────────────────
        elif act == "move":
            x, y = action.get("x"), action.get("y")
            pyautogui.moveTo(int(x), int(y), duration=0.3)
            return True, f"Moved to ({x}, {y})"

        # ── Drag ──────────────────────────────────────────────
        elif act == "drag":
            x1, y1 = action.get("x1"), action.get("y1")
            x2, y2 = action.get("x2"), action.get("y2")
            pyautogui.drag(int(x1), int(y1), int(x2-x1), int(y2-y1),
                          duration=0.5, button='left')
            return True, f"Dragged ({x1},{y1}) → ({x2},{y2})"

        # ── Wait ──────────────────────────────────────────────
        elif act == "wait":
            secs = action.get("seconds", 1)
            time.sleep(float(secs))
            return True, f"Waited {secs}s"

        # ── Open URL directly ─────────────────────────────────
        elif act == "open_url":
            url = action.get("url", "")
            if not url.startswith("http"):
                url = "https://" + url
            webbrowser.open(url)
            time.sleep(2)
            return True, f"Opened {url}"

        # ── Run shell command ─────────────────────────────────
        elif act == "run_command":
            cmd     = action.get("command", "")
            blocked = ["rm -rf", "del /f", "format", "shutdown /s",
                      "rmdir /s", ":(){:|:&};:"]
            if any(b.lower() in cmd.lower() for b in blocked):
                return False, f"Blocked dangerous command: {cmd}"
            result = subprocess.run(cmd, shell=True, capture_output=True,
                                   text=True, timeout=15)
            out = (result.stdout + result.stderr).strip()[:200]
            return True, f"Command: {cmd}\nOutput: {out}"

        # ── Screenshot (for verification) ─────────────────────
        elif act == "screenshot":
            screenshot()
            return True, "Screenshot taken"

        # ── Done signal ───────────────────────────────────────
        elif act == "done":
            return True, action.get("message", "Task complete.")

        # ── Fail signal ───────────────────────────────────────
        elif act == "fail":
            return False, action.get("message", "Task failed.")

        else:
            return False, f"Unknown action: {act}"

    except Exception as e:
        return False, f"Action failed: {e}"


# =============================================================
#  Core agent loop — one subtask at a time
# =============================================================
STEP_PROMPT = """You are controlling a Windows PC to complete a task.

Current task: {task}
Steps completed so far: {history}
Attempt: {attempt}/5

Look at the screenshot and decide the SINGLE NEXT ACTION to take.

Return ONLY a JSON object with ONE action:

For clicking: {{"action": "click", "x": 123, "y": 456, "description": "what you're clicking"}}
For typing: {{"action": "type", "text": "text to type"}}
For special characters or long text: {{"action": "type_paste", "text": "text"}}
For key combos: {{"action": "key", "keys": "ctrl+s"}}
For scrolling: {{"action": "scroll", "x": 500, "y": 400, "amount": 3}}
For waiting: {{"action": "wait", "seconds": 1}}
For opening URLs directly: {{"action": "open_url", "url": "https://example.com"}}
For running commands: {{"action": "run_command", "command": "cmd /c start code"}}
If task is COMPLETE: {{"action": "done", "message": "what was accomplished"}}
If task is IMPOSSIBLE: {{"action": "fail", "message": "why it failed"}}

Rules:
- Return ONLY the JSON, nothing else
- Be precise with coordinates — click the CENTER of elements
- If you need to open an app, use run_command with the executable name
- After typing in a search bar, use key enter to confirm
- If something didn't work, try a different approach
"""

PLAN_PROMPT = """Break down this task into clear subtasks:
Task: {task}

Return a JSON array of subtask strings. Keep each subtask simple and atomic.
Example: ["open VS Code", "create new file", "type the code", "save the file"]

Return ONLY the JSON array."""


def run_subtask(task: str, callback=None, max_steps: int = 30) -> tuple[bool, str]:
    """
    Run a single subtask using the agent loop.
    Takes screenshot → Gemini decides action → execute → repeat.

    Args:
        task: what to do
        callback: called with status updates
        max_steps: maximum actions before giving up

    Returns:
        (success, final_message)
    """
    history = []
    log     = lambda msg: (print(f"[agent] {msg}"), callback(msg) if callback else None)

    log(f"Starting subtask: {task}")

    for step in range(1, max_steps + 1):
        # Take fresh screenshot
        img_path = screenshot()

        # Ask Gemini what to do next
        prompt = STEP_PROMPT.format(
            task=task,
            history=json.dumps(history[-5:]) if history else "none",
            attempt=step
        )

        raw = ask_gemini(prompt, use_pro=False, img_path=img_path)
        action = parse_json(raw)

        if not action:
            log(f"Step {step}: Could not parse action — retrying")
            time.sleep(1)
            continue

        log(f"Step {step}: {action}")

        # Execute the action
        success, message = execute_action(action)
        history.append({"step": step, "action": action, "result": message})

        log(f"  → {message}")

        # Check if done or failed
        if action.get("action") == "done":
            return True, message

        if action.get("action") == "fail":
            return False, message

        if not success:
            log(f"  Action failed — Gemini will try differently next step")

        # Small pause between actions
        time.sleep(0.5)

    return False, f"Task exceeded {max_steps} steps without completion"


def run_task(task: str, callback=None) -> str:
    """
    Run a complete task — decomposes into subtasks if complex.

    Args:
        task: natural language task description
        callback: called with status updates (for UI)

    Returns:
        Final result string
    """
    log = lambda msg: (print(f"[computer_agent] {msg}"),
                      callback(msg) if callback else None)

    log(f"Task received: {task}")

    # ── Decide if task needs decomposition ────────────────────
    # Simple heuristic — if task has multiple verbs, decompose it
    complex_keywords = ["then", "and then", "after that", "also", "create",
                       "write", "build", "setup", "install", "configure"]
    is_complex = any(kw in task.lower() for kw in complex_keywords)

    if is_complex:
        log("Complex task — decomposing into subtasks...")

        # Take screenshot for context
        img_path = screenshot()
        plan_prompt = PLAN_PROMPT.format(task=task)
        raw = ask_gemini(plan_prompt, use_pro=True, img_path=img_path)
        subtasks = parse_json(raw)

        if not subtasks or not isinstance(subtasks, list):
            log("Could not decompose — running as single task")
            subtasks = [task]
        else:
            log(f"Subtasks: {subtasks}")
    else:
        subtasks = [task]

    # ── Run each subtask ──────────────────────────────────────
    results = []
    for i, subtask in enumerate(subtasks):
        log(f"\nSubtask {i+1}/{len(subtasks)}: {subtask}")
        success, message = run_subtask(subtask, callback=callback)
        results.append(f"{'✓' if success else '✗'} {subtask}: {message}")

        if not success:
            log(f"Subtask failed: {message}")
            # Continue to next subtask instead of stopping

        # Brief pause between subtasks
        time.sleep(1)

    summary = "\n".join(results)
    log(f"\nTask complete:\n{summary}")
    return summary


# =============================================================
#  Background session — runs tasks in a queue
# =============================================================
class AgentSession:
    """
    Background agent session.
    Add tasks to the queue, agent works through them.
    Non-blocking — Darmyth stays responsive while agent works.
    """

    def __init__(self, on_update=None, on_complete=None):
        """
        Args:
            on_update: called with status strings during execution
            on_complete: called when a task finishes
        """
        self.on_update   = on_update   or (lambda msg: print(f"[session] {msg}"))
        self.on_complete = on_complete or (lambda msg: print(f"[session] Done: {msg}"))
        self._queue      = queue.Queue()
        self._running    = False
        self._thread     = None
        self._current    = None

    def add_task(self, task: str):
        """Add a task to the queue."""
        self._queue.put(task)
        self.on_update(f"Task queued: {task}")
        if not self._running:
            self.start()

    def _worker(self):
        """Background worker — processes tasks from queue."""
        self._running = True
        while self._running:
            try:
                task = self._queue.get(timeout=1)
                self._current = task
                self.on_update(f"Starting: {task}")

                result = run_task(task, callback=self.on_update)
                self.on_complete(result)
                self._current = None
                self._queue.task_done()

            except queue.Empty:
                if self._queue.empty():
                    self._running = False
                    break
            except Exception as e:
                self.on_update(f"Error: {e}")

    def start(self):
        """Start background worker thread."""
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        print("[session] Agent session started.")

    def stop(self):
        """Stop the background worker."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        print("[session] Agent session stopped.")

    @property
    def is_busy(self) -> bool:
        return self._current is not None

    @property
    def current_task(self) -> str:
        return self._current or "idle"

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()


# =============================================================
#  Quick test
# =============================================================
if __name__ == "__main__":
    import sys

    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not in config/.env")
        print("Get it free at aistudio.google.com")
        sys.exit(1)

    print("Darmyth Computer Agent")
    print("=" * 50)
    print("The agent will control your PC to complete tasks.")
    print("Move mouse to TOP-LEFT corner to emergency stop.")
    print("Type 'quit' to exit\n")

    def on_update(msg):
        print(f"  → {msg}")

    def on_complete(msg):
        print(f"\nDone:\n{msg}\n")
        print("You: ", end="", flush=True)

    session = AgentSession(on_update=on_update, on_complete=on_complete)

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
        # Wait for task if running interactively
        while session.is_busy:
            time.sleep(0.5)

    session.stop()
    print("Goodbye.")