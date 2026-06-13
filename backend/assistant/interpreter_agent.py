# =============================================================
#  Darmyth — backend/assistant/interpreter_agent.py
#  PC control using Open Interpreter + Groq
#  No screenshots, no coordinates — just code execution
#  Groq writes the code, your PC runs it
# =============================================================

import os
import threading
import queue
import time
from pathlib import Path
from dotenv import load_dotenv

# ── Load config ───────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=BASE_DIR / "config" / ".env", override=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ── Obsidian vault path ───────────────────────────────────────
import yaml
with open(BASE_DIR / "config" / "settings.yaml") as f:
    SETTINGS = yaml.safe_load(f)
VAULT_PATH = SETTINGS["memory"]["notes_path"]


# =============================================================
#  Obsidian tools — direct file system, no screen needed
# =============================================================
class ObsidianTools:
    """
    Direct Obsidian vault operations.
    Much faster and more reliable than screen control.
    """

    def __init__(self, vault_path: str = VAULT_PATH):
        self.vault = Path(vault_path)

    def create_note(self, title: str, content: str = "",
                    folder: str = "") -> str:
        """Create a new note in the vault."""
        if folder:
            target_dir = self.vault / folder
            target_dir.mkdir(parents=True, exist_ok=True)
        else:
            target_dir = self.vault

        # Clean filename
        filename = title.strip().replace("/", "-").replace("\\", "-") + ".md"
        filepath = target_dir / filename

        if not content:
            content = f"# {title}\n\n"

        filepath.write_text(content, encoding="utf-8")
        print(f"[obsidian] Created: {filepath}")
        return f"Created note '{title}' at {filepath}"

    def append_to_note(self, title: str, content: str) -> str:
        """Append content to an existing note."""
        # Search for the note
        matches = list(self.vault.rglob(f"*{title}*.md"))
        if not matches:
            return f"Note '{title}' not found. Use create_note first."

        filepath = matches[0]
        existing = filepath.read_text(encoding="utf-8")
        filepath.write_text(existing + "\n" + content, encoding="utf-8")
        return f"Appended to '{filepath.name}'"

    def read_note(self, title: str) -> str:
        """Read a note's content."""
        matches = list(self.vault.rglob(f"*{title}*.md"))
        if not matches:
            return f"Note '{title}' not found."
        return matches[0].read_text(encoding="utf-8")

    def list_notes(self, folder: str = "") -> list:
        """List all notes in vault or a folder."""
        search_path = self.vault / folder if folder else self.vault
        return [str(p.relative_to(self.vault))
                for p in search_path.rglob("*.md")]

    def add_link(self, from_note: str, to_note: str) -> str:
        """Add an Obsidian wiki-link from one note to another."""
        matches = list(self.vault.rglob(f"*{from_note}*.md"))
        if not matches:
            return f"Note '{from_note}' not found."

        filepath = matches[0]
        existing = filepath.read_text(encoding="utf-8")
        link     = f"\n[[{to_note}]]\n"
        filepath.write_text(existing + link, encoding="utf-8")
        return f"Added link to [[{to_note}]] in '{filepath.name}'"

    def create_daily_note(self) -> str:
        """Create today's daily note."""
        from datetime import datetime
        today   = datetime.now()
        title   = today.strftime("%Y-%m-%d")
        content = f"# {today.strftime('%A, %B %d, %Y')}\n\n## Tasks\n- \n\n## Notes\n\n"
        return self.create_note(title, content, folder="Daily Notes")

    def search_notes(self, query: str) -> list:
        """Search note contents for a query string."""
        results = []
        for note in self.vault.rglob("*.md"):
            try:
                content = note.read_text(encoding="utf-8")
                if query.lower() in content.lower():
                    results.append(str(note.relative_to(self.vault)))
            except Exception:
                pass
        return results


# =============================================================
#  Open Interpreter setup with Groq
# =============================================================
def get_interpreter():
    """
    Create and configure Open Interpreter instance with Groq.
    """
    try:
        from interpreter import interpreter
    except ImportError:
        print("[interpreter] open-interpreter not installed.")
        print("[interpreter] Run: pip install open-interpreter")
        return None

    # Configure to use Groq
    interpreter.llm.model          = "groq/llama-3.3-70b-versatile"
    interpreter.llm.api_key        = GROQ_API_KEY
    interpreter.llm.api_base       = "https://api.groq.com/openai/v1"
    interpreter.llm.max_tokens     = 4096
    interpreter.llm.context_window = 8192

    # Safety settings
    interpreter.auto_run           = True   # don't ask confirmation every step
    interpreter.safe_mode          = "off"  # trust Groq's code
    interpreter.verbose            = False

    # System prompt — tell it about Darmyth's context
    interpreter.system_message = f"""You are Darmyth's execution engine.
You control a Windows 11 PC by writing and running Python and shell code.

Key paths:
- Obsidian vault: {VAULT_PATH}
- Project folder: {BASE_DIR}
- Desktop: C:/Users/AADITYA/Desktop

When opening apps, use subprocess.Popen() or os.startfile().
When managing files, use pathlib.Path.
When controlling the browser, use webbrowser.open().
When typing or clicking, use pyautogui.
Always confirm what you did at the end.
Keep responses concise."""

    return interpreter


# =============================================================
#  Hybrid agent — code for most tasks, vision for UI tasks
# =============================================================
# Tasks that need screen vision (can't be done with code alone)
VISION_TASKS = [
    "click", "find on screen", "what do you see",
    "scroll to", "select text", "drag", "resize window"
]

def needs_vision(task: str) -> bool:
    """Check if task needs screen vision or can be done with code."""
    return any(kw in task.lower() for kw in VISION_TASKS)


def run_with_interpreter(task: str,
                          callback=None) -> str:
    """
    Run a task using Open Interpreter + Groq.
    Returns result string.
    """
    log = lambda msg: (print(f"[interpreter_agent] {msg}"),
                      callback(msg) if callback else None)

    interp = get_interpreter()
    if not interp:
        return "Open Interpreter not available."

    log(f"Running: {task}")

    result_parts = []
    try:
        for chunk in interp.chat(task, stream=True, display=False):
            if isinstance(chunk, dict):
                if chunk.get("type") == "message":
                    content = chunk.get("content", "")
                    if content:
                        result_parts.append(content)
                        log(content)
                elif chunk.get("type") == "code":
                    code = chunk.get("content", "")
                    if code:
                        log(f"Executing:\n{code}")
                elif chunk.get("type") == "output":
                    output = chunk.get("content", "")
                    if output:
                        log(f"Output: {output}")

        return " ".join(result_parts) or "Task completed."

    except Exception as e:
        log(f"Error: {e}")
        return f"Failed: {e}"


# =============================================================
#  Background session with task queue
# =============================================================
class InterpreterSession:
    """
    Background session — runs tasks in a queue.
    Non-blocking, Darmyth stays responsive.
    """

    def __init__(self, on_update=None, on_complete=None):
        self.on_update   = on_update   or (lambda m: print(f"[session] {m}"))
        self.on_complete = on_complete or (lambda m: print(f"[session] Done: {m}"))
        self._queue      = queue.Queue()
        self._running    = False
        self._thread     = None
        self._current    = None
        self._interp     = None

    def _get_interp(self):
        """Lazy load interpreter — reuse across tasks."""
        if self._interp is None:
            self._interp = get_interpreter()
        return self._interp

    def add_task(self, task: str):
        """Add task to queue."""
        self._queue.put(task)
        self.on_update(f"Queued: {task}")
        if not self._running:
            self._start_worker()

    def _start_worker(self):
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _worker(self):
        self._running = True
        interp = self._get_interp()

        while self._running:
            try:
                task = self._queue.get(timeout=2)
                self._current = task
                self.on_update(f"Starting: {task}")

                result_parts = []
                try:
                    for chunk in interp.chat(task, stream=True, display=False):
                        if isinstance(chunk, dict):
                            if chunk.get("type") == "message":
                                content = chunk.get("content", "")
                                if content:
                                    result_parts.append(content)
                                    self.on_update(content)
                            elif chunk.get("type") == "code":
                                self.on_update(f"Running code: {chunk.get('content','')[:80]}...")
                            elif chunk.get("type") == "output":
                                self.on_update(f"→ {chunk.get('content','')[:100]}")

                    result = " ".join(result_parts) or "Done."
                    self.on_complete(result)

                except Exception as e:
                    self.on_complete(f"Error: {e}")

                self._current = None
                self._queue.task_done()

            except queue.Empty:
                if self._queue.empty():
                    self._running = False
                    break

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)

    @property
    def is_busy(self) -> bool:
        return self._current is not None

    @property
    def current_task(self) -> str:
        return self._current or "idle"


# =============================================================
#  Quick test
# =============================================================
if __name__ == "__main__":
    import sys

    print("Darmyth Interpreter Agent")
    print("=" * 50)
    print("Groq writes code → your PC runs it")
    print("Type 'quit' to exit\n")

    if not GROQ_API_KEY:
        print("ERROR: GROQ_API_KEY not in config/.env")
        sys.exit(1)

    # Test Obsidian tools directly first
    print("Testing Obsidian tools...")
    obs = ObsidianTools()
    notes = obs.list_notes()
    print(f"Found {len(notes)} notes in vault.\n")

    session = InterpreterSession(
        on_update=lambda m: print(f"  → {m}"),
        on_complete=lambda m: print(f"\nDone: {m}\n\nYou: ", end="", flush=True)
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

        # Check if it's an Obsidian task — handle directly without interpreter
        task_lower = task.lower()
        if any(kw in task_lower for kw in ["create note", "new note", "obsidian"]):
            if "create" in task_lower and "note" in task_lower:
                # Extract note name
                import re
                match = re.search(r'["\']([^"\']+)["\']|named?\s+(\w+)|called?\s+(\w+)', task, re.IGNORECASE)
                if match:
                    name = next(g for g in match.groups() if g)
                    result = obs.create_note(name)
                    print(f"  → {result}\n\nYou: ", end="", flush=True)
                    continue

        session.add_task(task)
        while session.is_busy:
            time.sleep(0.3)

    session.stop()
    print("Goodbye.")