"""Validate GPT-4o vision OCR on a saved SunSirs chart image.

Run after scout_sunsirs.py has saved data/mi/scout_toluene.png.
"""
import base64
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

IMG_PATH = Path("data/mi/scout_toluene.png")
PROMPT_PATH = Path("app/prompts/chart_ocr.txt")

if not IMG_PATH.exists():
    print(f"ERROR: {IMG_PATH} not found. Run scripts/scout_sunsirs.py first.")
    sys.exit(1)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
prompt = PROMPT_PATH.read_text()
b64 = base64.b64encode(IMG_PATH.read_bytes()).decode()

print(f"Sending {IMG_PATH} to GPT-4o vision...")
resp = client.chat.completions.create(
    model="gpt-4o",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ],
    }],
    temperature=0.1,
)

raw = resp.choices[0].message.content or ""
print("\n--- RAW RESPONSE ---")
print(raw)

# Strip markdown code fences if present
clean = raw.strip()
if clean.startswith("```"):
    clean = clean.split("```", 2)[-1] if clean.count("```") >= 2 else clean
    clean = clean.lstrip("json").strip().rstrip("```").strip()

try:
    data = json.loads(clean)
    points = data.get("points", [])
    print(f"\n--- PARSED OK ---")
    print(f"Commodity: {data.get('commodity')}")
    print(f"Unit: {data.get('unit')}")
    print(f"Year: {data.get('year')}")
    print(f"Points extracted: {len(points)}")
    if points:
        print(f"Date range: {points[0]['date']} → {points[-1]['date']}")
        print(f"Price range: {min(p['price'] for p in points)} – {max(p['price'] for p in points)}")
    if len(points) >= 10:
        print("\nSUCCESS: OCR prompt working. Ready to build sunsirs.py ingestor.")
    else:
        print(f"\nWARNING: only {len(points)} points returned. Refine the prompt.")
except json.JSONDecodeError as e:
    print(f"\nERROR: GPT-4o did not return valid JSON: {e}")
    print("Refine chart_ocr.txt prompt.")
