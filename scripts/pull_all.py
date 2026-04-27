"""Batch-pull raw data for all customers in data/customers.json."""
import json

from app.config import CUSTOMERS_FILE, ensure_customer_dirs, raw_dir
from app.connectors import elixir as elixir_conn
from app.connectors import hubspot as hubspot_conn
from app.connectors import news as news_conn
from app.models import Customer


def main() -> None:
    customers = [Customer(**c) for c in json.loads(CUSTOMERS_FILE.read_text())]
    for c in customers:
        print(f"-> pulling raw data for {c.company_name} ({c.customer_id})")
        ensure_customer_dirs(c.customer_id)

        hs = hubspot_conn.pull(c.customer_id, c.hubspot_company_id)
        el = elixir_conn.pull(c.customer_id, c.elixir_customer_id)
        nw = news_conn.pull(c.customer_id, c.company_name)

        rd = raw_dir(c.customer_id)
        (rd / "hubspot.json").write_text(hs.model_dump_json(indent=2))
        (rd / "elixir.json").write_text(el.model_dump_json(indent=2))
        (rd / "news.json").write_text(nw.model_dump_json(indent=2))
        print(f"   emails={len(hs.emails)} orders={len(el.orders)} news={len(nw.items)}")


if __name__ == "__main__":
    main()
