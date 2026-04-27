from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ManufacturingProfile(BaseModel):
    products_made: list[str] = Field(default_factory=list)
    scale: str = ""
    likely_inputs: list[str] = Field(default_factory=list)


class Customer(BaseModel):
    customer_id: str
    company_name: str
    website: str | None = None
    industry: str
    sub_industry: list[str] | None = None
    segment: Literal["end_user", "distributor"]
    geography: str
    hubspot_company_id: str | None = None
    elixir_customer_id: str | None = None
    manufacturing_profile: ManufacturingProfile
    historical_context: str | None = None
    notes: str | None = None


class HubSpotEmail(BaseModel):
    id: str
    thread_id: str
    timestamp: datetime
    direction: Literal["incoming", "outgoing"]
    from_address: str
    to_addresses: list[str] = Field(default_factory=list)
    subject: str = ""
    body_text: str = ""


class HubSpotMeeting(BaseModel):
    id: str
    timestamp: datetime
    attendees: list[str] = Field(default_factory=list)
    title: str = ""
    notes: str | None = None


class HubSpotCall(BaseModel):
    id: str
    timestamp: datetime
    duration_seconds: int = 0
    transcript: str | None = None
    notes: str | None = None


class InquiredProduct(BaseModel):
    name: str
    deal_name: str = ""
    deal_stage: str | None = None
    deal_date: date | None = None
    quantity: float | None = None
    is_open_deal: bool = True


class HubSpotRaw(BaseModel):
    customer_id: str
    pulled_at: datetime
    emails: list[HubSpotEmail] = Field(default_factory=list)
    meetings: list[HubSpotMeeting] = Field(default_factory=list)
    calls: list[HubSpotCall] = Field(default_factory=list)
    inquired_products: list[InquiredProduct] = Field(default_factory=list)


class Order(BaseModel):
    order_id: str
    date: date
    products: list[dict] = Field(default_factory=list)
    total_value: float = 0.0
    currency: str = "INR"
    status: str = ""


class Inquiry(BaseModel):
    inquiry_id: str
    date: date
    products_requested: list[str] = Field(default_factory=list)
    status: str = ""
    converted_to_order: bool = False


class ElixirRaw(BaseModel):
    customer_id: str
    pulled_at: datetime
    orders: list[Order] = Field(default_factory=list)
    inquiries: list[Inquiry] = Field(default_factory=list)


class NewsItem(BaseModel):
    title: str
    url: str | None = None
    date: date
    source: str = ""
    snippet: str = ""
    category: Literal["company", "macro", "industry"]


class NewsRaw(BaseModel):
    customer_id: str
    pulled_at: datetime
    items: list[NewsItem] = Field(default_factory=list)


class ThreadSummary(BaseModel):
    thread_id: str
    date_start: date
    date_end: date
    participants: list[str] = Field(default_factory=list)
    summary: str
    open_items: list[str] = Field(default_factory=list)
    sentiment: Literal["positive", "neutral", "cooling", "cold"]
    key_products_discussed: list[str] = Field(default_factory=list)


class OrderAggregate(BaseModel):
    customer_id: str
    total_orders: int
    total_value_ytd: float
    last_order_date: date | None = None
    days_since_last_order: int | None = None
    top_products: list[dict] = Field(default_factory=list)
    inquiry_count: int = 0
    inquiry_to_order_rate: float = 0.0
    products_inquired_not_ordered: list[str] = Field(default_factory=list)
    open_order_products: list[str] = Field(default_factory=list)


class FilteredNewsItem(NewsItem):
    why_it_matters: str


class Stage1Output(BaseModel):
    customer_id: str
    generated_at: datetime
    thread_summaries: list[ThreadSummary] = Field(default_factory=list)
    order_aggregate: OrderAggregate
    filtered_news: list[FilteredNewsItem] = Field(default_factory=list)
    inquired_products: list[InquiredProduct] = Field(default_factory=list)


class PitchAngle(BaseModel):
    product_name: str
    rationale: str


class PrepBrief(BaseModel):
    customer_id: str
    company_name: str
    generated_at: datetime
    last_touchpoint: date | None = None
    days_since_touchpoint: int | None = None

    conversation_recap: str
    customer_snapshot: str
    whats_new: str
    market_context: str
    pitch_angles: list[PitchAngle] = Field(default_factory=list)
    conversation_starters: list[str] = Field(default_factory=list)
