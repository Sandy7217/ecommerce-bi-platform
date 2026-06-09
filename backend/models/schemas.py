from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


Role = Literal["super_admin", "admin", "manager", "analyst", "md", "viewer"]
InventoryStatus = Literal["OOS", "BROKEN", "INSTOCK", "UNKNOWN"]
CategoryValue = Literal[
    "Discontinue",
    "OOS",
    "Winter",
    "Dog styles",
    "NOOS",
    "NOOS(Green)",
    "NOOS(Yellow)",
    "NOOS(Red)",
    "NOOS(Potential)",
    "Green",
    "Yellow",
    "Red",
    "Dead",
    "Unknown",
]


class DateRangeParams(BaseModel):
    from_date: date | None = None
    to_date: date | None = None
    channel: str | None = None
    category: str | None = None


class SalesKpis(BaseModel):
    mtd_sales: float = 0
    mtd_qty: int = 0
    mtd_sales_lakh: float = 0
    yesterday_sales: float = 0
    yesterday_qty: int = 0
    return_pct: float = 0


class TrendPoint(BaseModel):
    date: date | str
    sales_value: float
    qty: int


class CategoryBreakdown(BaseModel):
    category: str
    sales_value: float
    qty: int
    sku_count: int


class StyleSalesRow(BaseModel):
    style_color: str
    category_new: str | None = None
    cross_category: str | None = None
    ros: float = 0
    mtd_sales: float = 0
    mtd_qty: int = 0
    growth_flag: str = "stable"
    doi: float = 0


class InventoryKpis(BaseModel):
    total_inventory: int = 0
    oos_pct: float = 0
    broken_pct: float = 0
    instock_pct: float = 0
    oos_count: int = 0
    broken_count: int = 0


class InventoryStyleRow(BaseModel):
    style_color: str
    total_inventory: int = 0
    status: str = "UNKNOWN"
    ros_30d: float = 0
    doi: float = 0
    priority: str = "Do Not Replenish"
    replenishment_qty: int | None = None


class CategoryApprovalRequest(BaseModel):
    style_colors: list[str]
    notes: str | None = None
    override_by: str | None = None


class DiscontinueRequest(BaseModel):
    style_colors: list[str]
    notes: str | None = None
    override_by: str | None = None


class AssistantMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class AssistantChatRequest(BaseModel):
    message: str
    conversation_history: list[AssistantMessage] = Field(default_factory=list)


class AssistantChatResponse(BaseModel):
    answer: str
    intent: str | None = None
    summary_cards: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    tables: list[dict[str, Any]] = Field(default_factory=list)
    charts: list[dict[str, Any]] = Field(default_factory=list)
    csv_files: list[dict[str, Any]] = Field(default_factory=list)
    used_sources: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


class NotificationConfig(BaseModel):
    whatsapp_to: str | None = None
    email_to: str | None = None
    daily_enabled: bool = True
    weekly_enabled: bool = True
    oos_alert_enabled: bool = True
    rto_spike_threshold_pct: float = 20


class UserCreate(BaseModel):
    email: str
    name: str | None = None
    role: Role = "viewer"


class UserUpdate(BaseModel):
    name: str | None = None
    role: Role | None = None
    is_active: bool | None = None


class UserRole(BaseModel):
    user_id: str | None = None
    email: str
    name: str | None = None
    role: Role
    is_active: bool = True
    last_login: datetime | None = None
    created_at: datetime | None = None


class UploadResult(BaseModel):
    status: Literal["success", "error"] = "success"
    rows_processed: int = 0
    rows_inserted: int = 0
    rows_skipped: int = 0
    errors: list[str] = Field(default_factory=list)


class ReplenishmentRow(BaseModel):
    style_color: str
    replenishment_qty: int
    replenishment_date: date
    uploaded_by: str | None = None
    notes: str | None = None


class ForecastRow(BaseModel):
    style_color: str
    forecast_30d: float
    forecast_60d: float
    forecast_90d: float


class PipelineStatus(BaseModel):
    status: str
    last_refresh: datetime | None = None
    uploads: list[dict[str, Any]] = Field(default_factory=list)
