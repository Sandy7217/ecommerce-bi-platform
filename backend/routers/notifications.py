from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.models.schemas import NotificationConfig
from backend.routers.common import DEMO_SKUS, rows_or_demo
from backend.security import ADMIN_ROLES, require_roles
from backend.services.alert_engine import build_alert_count, build_daily_brief, build_replenishment_rows
from backend.services.email_service import send_weekly_summary
from backend.services.whatsapp import send_daily_whatsapp_report

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/daily_brief")
def daily_brief():
    sku_rows = rows_or_demo("sku_master", DEMO_SKUS)
    rows = build_replenishment_rows(sku_rows)
    urgent_count = build_alert_count(sku_rows)["count"]
    return build_daily_brief({"urgent_count": urgent_count, "fast_movers": rows[:3], "top_channel": "Myntra"})


@router.post("/whatsapp/test", dependencies=[Depends(require_roles(*ADMIN_ROLES))])
def whatsapp_test(config: NotificationConfig):
    return send_daily_whatsapp_report(daily_brief(), to=config.whatsapp_to)


@router.post("/email/test", dependencies=[Depends(require_roles(*ADMIN_ROLES))])
def email_test(config: NotificationConfig):
    if not config.email_to:
        return {"status": "skipped", "reason": "email_to is required"}
    return send_weekly_summary(str(config.email_to), daily_brief())
