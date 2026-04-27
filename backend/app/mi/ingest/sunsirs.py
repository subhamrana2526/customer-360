"""SunSirs chart ingestor — fetches chart images and OCRs them via GPT-4o vision."""
import base64
import json
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

GRAPH_URL = "https://graph.100ppi.com/?w=550&h=332&c=p&id={id}&state=english"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "image/png,image/*;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"
MIN_POINTS = 5


def _ocr_prompt() -> str:
    return (PROMPTS_DIR / "chart_ocr.txt").read_text()


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        # parts[1] is the content (possibly starting with "json\n")
        text = parts[1].lstrip("json").strip() if len(parts) >= 2 else text
    return text


def fetch_chart_image(sunsirs_id: int, referer_id: int | None = None) -> bytes:
    url = GRAPH_URL.format(id=sunsirs_id)
    headers = {
        **HEADERS,
        "Referer": f"https://www.sunsirs.com/uk/prodetail-{referer_id or sunsirs_id}.html",
    }
    r = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
    r.raise_for_status()
    ct = r.headers.get("content-type", "")
    if "image" not in ct:
        raise ValueError(f"Expected image, got {ct}: {r.text[:200]}")
    return r.content


def ocr_chart(image_bytes: bytes) -> list[dict]:
    """Send chart image to GPT-4o vision, return [{date, price}] sorted ascending."""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    b64 = base64.b64encode(image_bytes).decode()
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": _ocr_prompt()},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        }],
        temperature=0.1,
    )
    raw = resp.choices[0].message.content or ""
    data = json.loads(_strip_fences(raw))
    points = data.get("points", [])
    return sorted(points, key=lambda p: p["date"])


def ingest_factor(factor: dict) -> list[dict]:
    """Fetch + OCR one factor. Returns points or [] on failure."""
    sid = factor["sunsirs_id"]
    name = factor["name"]
    try:
        image = fetch_chart_image(sid)
        points = ocr_chart(image)
        if len(points) < MIN_POINTS:
            print(f"  [warn] {name}: only {len(points)} points returned, skipping")
            return []
        return points
    except Exception as e:
        print(f"  [error] {name} (id={sid}): {e}")
        return []


def ingest_all(factors: list[dict]) -> dict[str, list[dict]]:
    """Run OCR ingestion for all SunSirs factors. Returns {factor_id: [points]}."""
    sunsirs_factors = [f for f in factors if f.get("source") == "sunsirs" and f.get("sunsirs_id")]
    results: dict[str, list[dict]] = {}

    print(f"Ingesting {len(sunsirs_factors)} SunSirs factors...")
    for i, factor in enumerate(sunsirs_factors, 1):
        print(f"[{i}/{len(sunsirs_factors)}] {factor['name']} (id={factor['sunsirs_id']})...")
        points = ingest_factor(factor)
        if points:
            results[factor["id"]] = points
            print(f"  -> {len(points)} points ({points[0]['date']} → {points[-1]['date']})")
        # Small delay to avoid hammering the CDN
        time.sleep(0.5)

    return results
