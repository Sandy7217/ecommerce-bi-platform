from __future__ import annotations

from typing import Any

import httpx

from backend.config import get_settings


def send_email(to: str, subject: str, html: str, text: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    if not settings.resend_api_key:
        return {"status": "skipped", "reason": "RESEND_API_KEY is not configured", "to": to, "subject": subject}
    payload = {
        "from": settings.resend_from_email,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text
    response = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    return {"status": "sent", "response": response.json()}


def send_weekly_summary(to: str, metrics: dict[str, Any]) -> dict[str, Any]:
    html = f"""
    <h1>E-Commerce BI Weekly Summary</h1>
    <p>MTD Sales: Rs {metrics.get('sales_cr', 0)} Cr</p>
    <p>MTD Qty: {metrics.get('qty', 0)}</p>
    <p>Return %: {metrics.get('return_pct', 0)}%</p>
    <p>Urgent replenishment styles: {metrics.get('urgent_count', 0)}</p>
    """
    return send_email(to=to, subject="E-Commerce BI Weekly Summary", html=html)
