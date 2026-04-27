"""Run Stage 1 for all customers using cached raw data."""
import json
from datetime import datetime, timezone

from app.config import CUSTOMERS_FILE, ensure_customer_dirs, raw_dir, stage1_dir
from app.models import Customer, ElixirRaw, HubSpotRaw, NewsRaw, Stage1Output
from app.stage1.news_filter import filter_news
from app.stage1.orders import aggregate
from app.stage1.threads import summarize_threads


def main() -> None:
    customers = [Customer(**c) for c in json.loads(CUSTOMERS_FILE.read_text())]
    for c in customers:
        print(f"-> stage1 for {c.company_name} ({c.customer_id})")
        ensure_customer_dirs(c.customer_id)
        rd = raw_dir(c.customer_id)

        hs = HubSpotRaw(**json.loads((rd / "hubspot.json").read_text()))
        el = ElixirRaw(**json.loads((rd / "elixir.json").read_text()))
        nw = NewsRaw(**json.loads((rd / "news.json").read_text()))

        out = Stage1Output(
            customer_id=c.customer_id,
            generated_at=datetime.now(timezone.utc),
            thread_summaries=summarize_threads(hs),
            order_aggregate=aggregate(el),
            filtered_news=filter_news(c, nw),
        )
        (stage1_dir(c.customer_id) / "stage1.json").write_text(out.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
