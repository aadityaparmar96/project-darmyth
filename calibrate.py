# Calibration test — shows exactly where Gemini thinks things are
# vs where PyAutoGUI actually clicks
import os
import base64
import json
import pyautogui
import time
from PIL import Image
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv("config/.env", override=True)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

PHYSICAL_W, PHYSICAL_H = pyautogui.size()
print(f"Physical screen: {PHYSICAL_W}x{PHYSICAL_H}")

# Test 1: Take screenshot at FULL physical resolution
print("\nTest 1: Full resolution screenshot")
img = pyautogui.screenshot()
img.save("cal_full.png")
print(f"Screenshot size: {img.size}")

with open("cal_full.png", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

response = client.chat.completions.create(
    model="models/gemini-2.5-flash",
    messages=[{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        {"type": "text", "text": f"""This screenshot is {img.size[0]}x{img.size[1]} pixels.
Find the Windows taskbar search bar (the search icon or box at the bottom center of the screen).
Return ONLY JSON: {{"x": <x_coord>, "y": <y_coord>, "width": {img.size[0]}, "height": {img.size[1]}}}"""}
    ]}],
    max_tokens=100,
)

raw = response.choices[0].message.content.strip()
print(f"Gemini says: {raw}")

try:
    clean = raw
    if "{" in clean:
        clean = clean[clean.find("{"):clean.rfind("}")+1]
    data = json.loads(clean)
    gx, gy = data.get("x"), data.get("y")
    print(f"Gemini coords: ({gx}, {gy}) on {img.size[0]}x{img.size[1]} image")

    # Move mouse there WITHOUT clicking to verify
    print(f"\nMoving mouse to ({gx}, {gy}) in 3 seconds...")
    print("Watch where your mouse goes!")
    time.sleep(3)
    pyautogui.moveTo(gx, gy, duration=0.5)
    time.sleep(2)
    print(f"Mouse is now at: {pyautogui.position()}")
except Exception as e:
    print(f"Parse error: {e}")
    print(f"Raw: {raw}")