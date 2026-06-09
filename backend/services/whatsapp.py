from __future__ import annotations

from typing import Any

from backend.config import get_settings


DAILY_REPORT_TEMPLATE = """Daily Brief - {date}

MTD Sales: Rs {sales_cr} Cr
MTD Qty: {qty}
Return %: {return_pct}%
OOS: {oos_pct}% ({oos_count} styles)
Broken: {broken_pct}%

Fast Movers: {fast_movers}
Urgent Replenishment: {urgent_count} styles
Top Channel: {top_channel}

Powered by E-Commerce BI Platform
"""


def render_daily_report(metrics: dict[str, Any]) -> str:
    fast_movers = metrics.get("fast_movers") or []
    if isinstance(fast_movers, list):
        fast_movers = ", ".join(str(item.get("style_color", item)) for item in fast_movers[:3]) or "None"
    return DAILY_REPORT_TEMPLATE.format(fast_movers=fast_movers, **metrics)


def send_whatsapp_message(body: str, to: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    target = to or settings.whatsapp_to
    if not (settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_whatsapp_from and target):
        return {"status": "skipped", "reason": "Twilio WhatsApp env vars are not configured", "body": body}
    try:
        from twilio.rest import Client
    except ModuleNotFoundError:
        return {"status": "skipped", "reason": "Install requirements.txt to enable Twilio WhatsApp", "body": body}
    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    message = client.messages.create(body=body, from_=settings.twilio_whatsapp_from, to=target)
    return {"status": "sent", "sid": message.sid}


def send_daily_whatsapp_report(metrics: dict[str, Any], to: str | None = None) -> dict[str, Any]:
    return send_whatsapp_message(render_daily_report(metrics), to=to)
