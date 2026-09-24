"""Public unsubscribe for cycle-2 cold email (roadmap step 15, CAN-SPAM).

GET shows a confirmation page (link scanners must not unsubscribe people);
POST unsubscribes. Mail clients use the same URL for RFC 8058 one-click
(`List-Unsubscribe-Post: List-Unsubscribe=One-Click`).
"""

from html import escape
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from src.persistence.email_outreach_service import read_unsubscribe_token
from src.persistence.outreach_service import OutreachService

from ..dependencies import ApplicationContainer, get_container, get_outreach_service

router = APIRouter(prefix="/api/v1/public/unsubscribe", tags=["public unsubscribe"])


def _page(title: str, text: str, form: str = "", status_code: int = 200) -> HTMLResponse:
    html = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{escape(title)}</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:32rem;margin:4rem auto;padding:0 1rem;color:#1a1a1a}"
        "button{font:inherit;padding:.6rem 1.2rem;border:0;border-radius:.4rem;background:#1a1a1a;color:#fff;cursor:pointer}</style>"
        f"</head><body><h1>{escape(title)}</h1><p>{escape(text)}</p>{form}</body></html>"
    )
    return HTMLResponse(html, status_code=status_code)


def _invalid() -> HTMLResponse:
    return _page("Link not valid", "This unsubscribe link is not valid. Reply to the email with \"no\" instead.", status_code=404)


@router.get("/{token}", response_class=HTMLResponse)
def confirm_unsubscribe(
    token: str,
    container: Annotated[ApplicationContainer, Depends(get_container)],
) -> HTMLResponse:
    parsed = read_unsubscribe_token(container.settings.account_security_encryption_key, token)
    if parsed is None:
        return _invalid()
    _, email = parsed
    form = f"<form method='post' action='{escape(token)}'><button type='submit'>Unsubscribe</button></form>"
    return _page("Unsubscribe", f"Stop all emails to {email}?", form)


@router.post("/{token}", response_class=HTMLResponse)
def unsubscribe(
    token: str,
    container: Annotated[ApplicationContainer, Depends(get_container)],
    service: Annotated[OutreachService, Depends(get_outreach_service)],
) -> HTMLResponse:
    parsed = read_unsubscribe_token(container.settings.account_security_encryption_key, token)
    if parsed is None:
        return _invalid()
    business_id, email = parsed
    service.unsubscribe(business_id, email)
    return _page("You are unsubscribed", f"We will not email {email} again.")
