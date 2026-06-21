# Run from project root: python debug_agent.py
import os
import base64
import pyautogui
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv("config/.env", override=True)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
print(f"Key loaded: {GEMINI_API_KEY[:8] if GEMINI_API_KEY else 'MISSING'}...\n")

client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# Take screenshot
img = pyautogui.screenshot()
img.save("debug_screen.png")
with open("debug_screen.png", "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()

prompt = """Look at this screenshot. I want to open Notepad.
Return ONLY a JSON object with the single next action.
Example: {"action": "run_command", "command": "notepad", "description": "opening notepad"}
Return ONLY the JSON object, no markdown, no explanation, no code blocks."""

for model in ["models/gemini-2.0-flash", "models/gemini-2.5-flash", "models/gemini-flash-latest"]:
    print(f"Trying model: {model}")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                    {"type": "text", "text": prompt}
                ]
            }],
            max_tokens=256,
            temperature=0.1,
        )
        raw = response.choices[0].message.content
        print(f"Raw response:\n{raw}\n")

        import json
        try:
            clean = raw.strip()
            if "```" in clean:
                parts = clean.split("```")
                for p in parts:
                    p = p.strip().lstrip("json").strip()
                    if p.startswith("{"):
                        clean = p
                        break
            result = json.loads(clean)
            print(f"Parsed OK: {result}")
            print(f"\nWorking model: {model}")
        except Exception as e:
            print(f"Parse failed: {e} — raw: {repr(clean[:200])}")
        break
    except Exception as e:
        print(f"Failed: {str(e)[:120]}\n")