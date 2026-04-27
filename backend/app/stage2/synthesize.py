"""Stage 2 — generate the PrepBrief from customer profile + Stage 1 output."""
import json
from datetime import datetime, timezone

from app.llm import call_json, load_prompt
from app.models import Customer, PitchAngle, PrepBrief, Stage1Output


def _last_touchpoint(stage1: Stage1Output):
    candidates = [s.date_end for s in stage1.thread_summaries]
    if stage1.order_aggregate.last_order_date:
        candidates.append(stage1.order_aggregate.last_order_date)
    return max(candidates) if candidates else None


def synthesize(customer: Customer, stage1: Stage1Output) -> PrepBrief:
    do_not_pitch = sorted(
        {p.name for p in stage1.inquired_products if p.is_open_deal}
        | set(stage1.order_aggregate.open_order_products)
    )

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
        .replace(
            "{inquired_products}",
            json.dumps([p.model_dump(mode="json") for p in stage1.inquired_products], indent=2),
        )
        .replace(
            "{do_not_pitch}",
            json.dumps(do_not_pitch, indent=2) if do_not_pitch else "[]",
        )
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
        conversation_recap=result.get("conversation_recap", ""),
        customer_snapshot=result.get("customer_snapshot", ""),
        whats_new=result.get("whats_new", ""),
        market_context=result.get("market_context", ""),
        pitch_angles=pitch_angles,
        conversation_starters=result.get("conversation_starters", []),
    )
