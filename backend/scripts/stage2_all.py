"""Run Stage 2 (synthesize PrepBriefs) for all customers."""
import json

from app.config import CUSTOMERS_FILE, brief_path, stage1_dir
from app.models import Customer, Stage1Output
from app.stage2.synthesize import synthesize


def main() -> None:
    customers = [Customer(**c) for c in json.loads(CUSTOMERS_FILE.read_text())]

    for c in customers:
        print(f"-> stage2 for {c.company_name} ({c.customer_id})")
        s1_path = stage1_dir(c.customer_id) / "stage1.json"
        if not s1_path.exists():
            print(f"   SKIP — no stage1.json (run stage1_all.py first)")
            continue
        s1 = Stage1Output(**json.loads(s1_path.read_text()))
        brief = synthesize(c, s1)
        brief_path(c.customer_id).write_text(brief.model_dump_json(indent=2))
        print(f"   wrote {brief_path(c.customer_id)}")


if __name__ == "__main__":
    main()
