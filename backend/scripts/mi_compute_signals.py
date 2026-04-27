"""Recompute and display all MI signals. Run after mi_ingest_all.py."""
import json
from pathlib import Path

from app.mi import signals

results = signals.all_signals()

print(f"{'Product':<25} {'Dir':<5} {'Change':>8}  Summary")
print("-" * 80)
for s in results:
    pct = round(s["pct_change"] * 100, 1)
    sign = "+" if pct > 0 else ""
    print(f"{s['product_name']:<25} {s['direction']:<5} {sign}{pct}%  — {s['summary_line']}")

out = Path("data/mi/signals_cache.json")
out.write_text(json.dumps(results, indent=2, default=str))
print(f"\nSaved {len(results)} signals → {out}")


if __name__ == "__main__":
    pass
