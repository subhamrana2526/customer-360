"""Scout: verify graph.100ppi.com chart image access via httpx."""
import sys
from pathlib import Path

import httpx

GRAPH_URL = "https://graph.100ppi.com/?w=550&h=332&c=p&id={id}&state=english"
TEST_IDS = {
    "toluene": 177,
    "lpg": 158,
    "caustic_soda": 368,
    "hcl": 355,
}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.sunsirs.com/uk/prodetail-177.html",
    "Accept": "image/png,image/*;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

OUT_DIR = Path("data/mi")
OUT_DIR.mkdir(parents=True, exist_ok=True)

all_ok = True
for name, sid in TEST_IDS.items():
    url = GRAPH_URL.format(id=sid)
    try:
        r = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=15)
        ct = r.headers.get("content-type", "")
        print(f"{name} (id={sid}): status={r.status_code}  content-type={ct}  size={len(r.content)} bytes")
        if r.status_code == 200 and "image" in ct:
            path = OUT_DIR / f"scout_{name}.png"
            path.write_bytes(r.content)
            print(f"  -> saved {path}")
        else:
            print(f"  -> FAILED. Response preview: {r.text[:300]}")
            all_ok = False
    except Exception as e:
        print(f"{name} (id={sid}): ERROR — {e}")
        all_ok = False

print()
if all_ok:
    print("SUCCESS: all charts fetched via httpx. Playwright NOT needed.")
    print("Next step: run scripts/test_ocr.py to validate GPT-4o vision.")
else:
    print("PARTIAL/FAIL: some charts blocked. Install Playwright fallback:")
    print("  pip install playwright && playwright install chromium")


if __name__ == "__main__":
    pass
