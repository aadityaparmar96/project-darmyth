# =============================================================
#  Darmyth — backend/rag/obsidian_tools.py
#  Direct Obsidian vault operations — no API needed
#  All operations are instant, offline, and free
# =============================================================

import re
import yaml
from pathlib import Path
from datetime import datetime

# ── Load settings ─────────────────────────────────────────────
BASE_DIR  = Path(__file__).resolve().parents[2]
YAML_PATH = BASE_DIR / "config" / "settings.yaml"

with open(YAML_PATH) as f:
    SETTINGS = yaml.safe_load(f)

VAULT_PATH = Path(SETTINGS["memory"]["notes_path"])


# =============================================================
#  Core vault operations
# =============================================================
class ObsidianVault:

    def __init__(self, vault_path: Path = VAULT_PATH):
        self.vault = vault_path
        if not self.vault.exists():
            print(f"[obsidian] Warning: vault not found at {vault_path}")

    # ── Find note ─────────────────────────────────────────────
    def find_note(self, title: str) -> Path | None:
        """Find a note by title (fuzzy match)."""
        title_clean = title.lower().strip()

        # Exact match first
        for note in self.vault.rglob("*.md"):
            if note.stem.lower() == title_clean:
                return note

        # Partial match
        for note in self.vault.rglob("*.md"):
            if title_clean in note.stem.lower():
                return note

        return None

    # ── Create note ───────────────────────────────────────────
    def create_note(self, title: str, content: str = "",
                    folder: str = "", tags: list = None) -> str:
        """
        Create a new note in the vault.
        Returns confirmation string.
        """
        # Build target path
        target_dir = self.vault / folder if folder else self.vault
        target_dir.mkdir(parents=True, exist_ok=True)

        # Clean filename
        filename = re.sub(r'[<>:"/\\|?*]', '-', title.strip()) + ".md"
        filepath = target_dir / filename

        # Check if already exists
        if filepath.exists():
            return f"Note '{title}' already exists. Use 'add to note' to append content."

        # Build note content
        now = datetime.now()
        header = f"# {title}\n"
        header += f"Created: {now.strftime('%Y-%m-%d %H:%M')}\n"
        if tags:
            header += f"Tags: {' '.join('#' + t for t in tags)}\n"
        header += "\n"

        full_content = header + (content + "\n" if content else "")
        filepath.write_text(full_content, encoding="utf-8")

        print(f"[obsidian] Created: {filepath}")
        return f"Created note '{title}'." + (f" in {folder}/" if folder else "")

    # ── Append to note ────────────────────────────────────────
    def append_to_note(self, title: str, content: str) -> str:
        """Append content to an existing note."""
        filepath = self.find_note(title)

        if not filepath:
            # Create it if it doesn't exist
            self.create_note(title)
            filepath = self.find_note(title)

        existing = filepath.read_text(encoding="utf-8")
        timestamp = datetime.now().strftime("%H:%M")
        new_content = existing + f"\n{content}\n"
        filepath.write_text(new_content, encoding="utf-8")

        print(f"[obsidian] Appended to: {filepath.name}")
        return f"Added to '{filepath.stem}'."

    # ── Read note ─────────────────────────────────────────────
    def read_note(self, title: str,
                  max_chars: int = 1000) -> str:
        """Read a note's content. Returns truncated content."""
        filepath = self.find_note(title)

        if not filepath:
            return f"No note found matching '{title}'."

        content = filepath.read_text(encoding="utf-8")
        if len(content) > max_chars:
            return content[:max_chars] + f"\n\n[...{len(content)-max_chars} more chars]"
        return content

    # ── Add link ──────────────────────────────────────────────
    def add_link(self, from_note: str, to_note: str) -> str:
        """Add an Obsidian [[wiki-link]] between two notes."""
        filepath = self.find_note(from_note)

        if not filepath:
            return f"Note '{from_note}' not found."

        existing = filepath.read_text(encoding="utf-8")

        # Don't add duplicate links
        if f"[[{to_note}]]" in existing:
            return f"Link to [[{to_note}]] already exists in '{from_note}'."

        new_content = existing.rstrip() + f"\n\n[[{to_note}]]\n"
        filepath.write_text(new_content, encoding="utf-8")

        print(f"[obsidian] Linked {from_note} → {to_note}")
        return f"Linked [[{to_note}]] in '{from_note}'."

    # ── Search notes ──────────────────────────────────────────
    def search_notes(self, query: str,
                     max_results: int = 5) -> str:
        """Search vault contents for a query."""
        query_lower = query.lower()
        results     = []

        for note in self.vault.rglob("*.md"):
            try:
                content = note.read_text(encoding="utf-8")
                if query_lower in content.lower():
                    # Find the matching line for context
                    lines = content.split("\n")
                    matching = [l.strip() for l in lines
                               if query_lower in l.lower() and l.strip()]
                    context = matching[0][:80] if matching else ""
                    results.append((note.stem, context))
            except Exception:
                pass

        if not results:
            return f"No notes found containing '{query}'."

        results = results[:max_results]
        lines   = [f"• {name}: {ctx}" for name, ctx in results]
        return f"Found {len(results)} notes matching '{query}':\n" + "\n".join(lines)

    # ── List notes ────────────────────────────────────────────
    def list_notes(self, folder: str = "",
                   max_results: int = 10) -> str:
        """List notes in the vault or a specific folder."""
        search_path = self.vault / folder if folder else self.vault
        notes = list(search_path.rglob("*.md"))

        if not notes:
            return f"No notes found in {'/' + folder if folder else 'vault'}."

        names = [str(n.relative_to(self.vault)) for n in notes[:max_results]]
        total = len(notes)
        result = f"{total} notes" + (f" in {folder}/" if folder else "") + ":\n"
        result += "\n".join(f"• {n}" for n in names)
        if total > max_results:
            result += f"\n...and {total - max_results} more"
        return result

    # ── Create daily note ─────────────────────────────────────
    def create_daily_note(self) -> str:
        """Create today's daily note with a structured template."""
        now   = datetime.now()
        title = now.strftime("%Y-%m-%d")
        day   = now.strftime("%A, %B %d, %Y")

        content = f"""## Tasks
- [ ] 

## Notes


## Ideas


## Links
"""
        return self.create_note(title, content, folder="Daily Notes")

    # ── Move note ─────────────────────────────────────────────
    def move_note(self, title: str, to_folder: str) -> str:
        """Move a note to a different folder."""
        filepath = self.find_note(title)
        if not filepath:
            return f"Note '{title}' not found."

        target_dir = self.vault / to_folder
        target_dir.mkdir(parents=True, exist_ok=True)
        new_path = target_dir / filepath.name
        filepath.rename(new_path)

        return f"Moved '{title}' to {to_folder}/."

    # ── Add tag ───────────────────────────────────────────────
    def add_tag(self, title: str, tag: str) -> str:
        """Add a tag to a note."""
        filepath = self.find_note(title)
        if not filepath:
            return f"Note '{title}' not found."

        content = filepath.read_text(encoding="utf-8")
        tag_str = f"#{tag}"

        if tag_str in content:
            return f"Tag {tag_str} already in '{title}'."

        # Add after first heading
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("#"):
                lines.insert(i + 1, f"Tags: {tag_str}")
                break
        else:
            lines.insert(0, f"Tags: {tag_str}")

        filepath.write_text("\n".join(lines), encoding="utf-8")
        return f"Added {tag_str} to '{title}'."


# =============================================================
#  Voice command parser
#  Converts natural language → vault operation
# =============================================================
_vault = None

def get_vault() -> ObsidianVault:
    global _vault
    if _vault is None:
        _vault = ObsidianVault()
    return _vault


def handle_obsidian_command(text: str) -> str | None:
    """
    Parse a voice command and execute the right vault operation.
    Returns result string, or None if not an Obsidian command.
    """
    t     = text.lower().strip()
    vault = get_vault()

    # ── Create note ───────────────────────────────────────────
    if any(p in t for p in ["create note", "new note", "make note",
                             "create a note", "make a note"]):
        # Extract title
        title = _extract_quoted(text) or _extract_after(t, [
            "create note called", "create note named", "create note",
            "new note called", "new note named", "new note",
            "make note called", "make note named", "make note",
            "create a note called", "create a note named", "create a note",
            "make a note called", "make a note named", "make a note",
        ])
        if not title:
            return "What should I call the note?"
        return vault.create_note(title)

    # ── Daily note ────────────────────────────────────────────
    if any(p in t for p in ["daily note", "today's note",
                             "create today", "note for today"]):
        return vault.create_daily_note()

    # ── Append to note ────────────────────────────────────────
    if any(p in t for p in ["add to", "append to", "write to",
                             "note down in", "add in"]):
        # "add to <note>: <content>" or "add to my <note> note <content>"
        parts = re.split(r'add to|append to|write to|note down in|add in',
                        t, maxsplit=1)
        if len(parts) > 1:
            rest = parts[1].strip()
            # Try to split note title from content
            colon_split = rest.split(":", 1)
            if len(colon_split) == 2:
                note_title = colon_split[0].strip().replace("my ", "").replace(" note", "")
                content    = colon_split[1].strip()
            else:
                # Use original casing for content
                orig_parts = re.split(r'add to|append to|write to|note down in|add in',
                                     text, maxsplit=1, flags=re.IGNORECASE)
                rest_orig  = orig_parts[1].strip() if len(orig_parts) > 1 else rest
                words      = rest_orig.split()
                note_title = words[0].replace("my", "").strip() if words else "notes"
                content    = " ".join(words[1:]) if len(words) > 1 else ""

            if not content:
                return f"What should I add to '{note_title}'?"
            return vault.append_to_note(note_title, content)

    # ── Read note ─────────────────────────────────────────────
    if any(p in t for p in ["read note", "open note", "show note",
                             "what's in my", "what is in my",
                             "read my", "show me my"]):
        title = _extract_quoted(text) or _extract_after(t, [
            "read note called", "read note", "open note", "show note",
            "what's in my", "what is in my", "read my", "show me my"
        ])
        title = title.replace(" note", "").strip() if title else ""
        if not title:
            return "Which note should I read?"
        return vault.read_note(title)

    # ── Search notes ──────────────────────────────────────────
    if any(p in t for p in ["search notes", "search my notes",
                             "find in notes", "look in notes",
                             "search for", "find notes about"]):
        query = _extract_after(t, [
            "search notes for", "search my notes for",
            "find in notes", "look in notes",
            "search for", "find notes about", "search notes"
        ])
        if not query:
            return "What should I search for?"
        return vault.search_notes(query)

    # ── List notes ────────────────────────────────────────────
    if any(p in t for p in ["list notes", "list my notes",
                             "show notes", "what notes do i have",
                             "list all notes"]):
        folder = _extract_after(t, ["list notes in", "show notes in",
                                   "notes in folder"]) or ""
        return vault.list_notes(folder)

    # ── Link notes ────────────────────────────────────────────
    if any(p in t for p in ["link", "connect note", "add link"]):
        # "link <note1> to <note2>"
        match = re.search(r'link (.+?) to (.+)', t)
        if match:
            from_note = match.group(1).strip()
            to_note   = match.group(2).strip()
            return vault.add_link(from_note, to_note)
        return "Say: link <note> to <other note>"

    # ── Move note ─────────────────────────────────────────────
    if any(p in t for p in ["move note", "move my note"]):
        match = re.search(r'move (?:note |my note )?(.+?) to (.+)', t)
        if match:
            title  = match.group(1).strip()
            folder = match.group(2).strip()
            return vault.move_note(title, folder)

    # ── Add tag ───────────────────────────────────────────────
    if any(p in t for p in ["add tag", "tag note", "tag the note"]):
        match = re.search(r'tag (?:note |the note )?(.+?) (?:with |as )(.+)', t)
        if match:
            title = match.group(1).strip()
            tag   = match.group(2).strip()
            return vault.add_tag(title, tag)

    return None   # not an Obsidian command


# ── Helpers ───────────────────────────────────────────────────
def _extract_quoted(text: str) -> str | None:
    """Extract text in quotes."""
    match = re.search(r'["\']([^"\']+)["\']', text)
    return match.group(1).strip() if match else None


def _extract_after(text: str, phrases: list) -> str:
    """Extract text after the first matching phrase."""
    for phrase in phrases:
        idx = text.lower().find(phrase)
        if idx != -1:
            result = text[idx + len(phrase):].strip()
            # Remove leading articles
            result = re.sub(r'^(a |an |the |my )', '', result, flags=re.IGNORECASE)
            return result.strip()
    return ""


# =============================================================
#  Quick test
# =============================================================
if __name__ == "__main__":
    print("Testing Darmyth Obsidian Tools\n")
    print(f"Vault: {VAULT_PATH}\n")

    vault = ObsidianVault()

    tests = [
        ("List notes",           lambda: vault.list_notes()),
        ("Create note",          lambda: vault.create_note("Darmyth Test Note", "This is a test.")),
        ("Append to note",       lambda: vault.append_to_note("Darmyth Test Note", "Added this line.")),
        ("Read note",            lambda: vault.read_note("Darmyth Test Note")),
        ("Search notes",         lambda: vault.search_notes("Darmyth")),
        ("Create daily note",    lambda: vault.create_daily_note()),
    ]

    for name, fn in tests:
        print(f"--- {name} ---")
        result = fn()
        print(result[:200] if result else "No result")
        print()

    print("\n--- Voice command parser ---")
    voice_tests = [
        "Create a note called 'Project Alpha'",
        "Create today's daily note",
        "Search my notes for Kael",
        "List my notes",
        "What's in my fungus note",
        "Add to my projects note: finish the Darmyth UI",
        "Link Chapter 1 to Chapter 2",
    ]

    for cmd in voice_tests:
        print(f"You: {cmd}")
        result = handle_obsidian_command(cmd)
        print(f"Darmyth: {result or '[not an Obsidian command]'}")
        print()