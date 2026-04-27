"""Stage 2 — generate the PrepBrief from customer profile + Stage 1 output."""
import json
from datetime import datetime, timezone

from app.llm import call_json, load_prompt
from app.models import Customer, PitchAngle, PrepBrief, Stage1Output


def _filter_catalog(customer: Customer, catalog: list[dict]) -> list[dict]:
    """Keep catalog items whose tags overlap with the customer's industry/inputs."""
    if not catalog:
        return []
    targets = {customer.industry.lower()}
    for s in customer.sub_industry or []:
        targets.add(s.lower())
    for p in customer.manufacturing_profile.likely_inputs:
        targets.add(p.lower())

    matched: list[dict] = []
    for item in catalog:
        tags = {t.lower() for t in item.get("tags", [])}
        name = (item.get("name") or "").lower()
        if tags & targets or any(t in name for t in targets):
            matched.append(item)
    return matched or catalog[:30]


def _last_touchpoint(stage1: Stage1Output):
    candidates = [s.date_end for s in stage1.thread_summaries]
    if stage1.order_aggregate.last_order_date:
        candidates.append(stage1.order_aggregate.last_order_date)
    return max(candidates) if candidates else None


def synthesize(
    customer: Customer,
    stage1: Stage1Output,
    product_catalog: list[dict],
) -> PrepBrief:
    filtered_catalog = _filter_catalog(customer, product_catalog)

    prompt = (
        load_prompt("brief_synthesis.txt")
        .replace("{customer_profile}", customer.model_dump_json(indent=2))
        .replace("{historical_context}", customer.historical_context or "(none on file)")
        .replace(
            "{thread_summaries}",
            json.dumps([s.model_dump(mode="json") for s in stage1.thread_summaries], indent=2),
        )
        .replace(
            "{order_aggregate}",
            stage1.order_aggregate.model_dump_json(indent=2),
        )
        .replace(
            "{filtered_news}",
            json.dumps([n.model_dump(mode="json") for n in stage1.filtered_news], indent=2),
        )
        .replace("{filtered_product_catalog}", json.dumps(filtered_catalog, indent=2))
    )

    result = call_json(prompt, purpose="synth", temperature=0.3)

    last_tp = _last_touchpoint(stage1)
    days_since = None
    if last_tp:
        days_since = (datetime.now(timezone.utc).date() - last_tp).days

    pitch_angles = [PitchAngle(**p) for p in result.get("pitch_angles", []) if isinstance(p, dict)]

    return PrepBrief(
        customer_id=customer.customer_id,
        company_name=customer.company_name,
        generated_at=datetime.now(timezone.utc),
        last_touchpoint=last_tp,
        days_since_touchpoint=days_since,
        tldr=result.get("tldr", ""),
        conversation_recap=result.get("conversation_recap", ""),
        customer_snapshot=result.get("customer_snapshot", ""),
        whats_new=result.get("whats_new", ""),
        market_context=result.get("market_context", ""),
        pitch_angles=pitch_angles,
        conversation_starters=result.get("conversation_starters", []),
    )
