"""Phase 4: Gmail API sending."""

import base64
import json
import logging
import os
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from backend.agent.state import NewsletterState

logger = logging.getLogger(__name__)

COUNTRY_NAMES = {
    "KR": "한국", "RU": "러시아", "VN": "베트남",
    "TH": "태국", "PH": "필리핀", "PK": "파키스탄",
}


def get_gmail_service():
    """Build Gmail API service using OAuth2 credentials."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
    creds = None
    token_path = Path(os.environ.get("GMAIL_TOKEN_FILE", ".gmail_token.json"))
    creds_path = Path(os.environ.get("GMAIL_CREDENTIALS_FILE", ".gmail_credentials.json"))

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not creds_path.exists():
                raise FileNotFoundError(f"Gmail credentials not found: {creds_path}")
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def create_email(sender: str, to: list[str], subject: str, html_body: str) -> dict:
    """Create a Gmail-compatible email message."""
    msg = MIMEMultipart("alternative")
    msg["From"] = sender
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw}


async def send_newsletter(state: NewsletterState) -> dict:
    """Send newsletters via Gmail API."""
    newsletters = state.get("newsletters", {})
    date_str = state.get("date_str", datetime.now().strftime("%Y%m%d"))
    sender = os.environ.get("GMAIL_SENDER", "skenbizst@gmail.com")
    send_results: dict[str, bool] = {}

    # Load recipients from database or environment
    # In SaaS mode, recipients come from the settings API
    default_recipients = os.environ.get("DEFAULT_RECIPIENTS", "").split(",")
    default_recipients = [r.strip() for r in default_recipients if r.strip()]

    try:
        service = get_gmail_service()
    except Exception as e:
        logger.error(f"Gmail auth failed: {e}")
        return {
            "send_results": {c: False for c in newsletters},
            "errors": state.get("errors", []) + [f"Gmail auth failed: {e}"],
            "current_phase": "sending",
            "phase_status": {**state.get("phase_status", {}), "sending": "failed"},
        }

    for country, html in newsletters.items():
        country_name = COUNTRY_NAMES.get(country, country)
        subject = f"[SK엔무브 MI] {country_name} 윤활유 시장 동향 ({date_str[:4]}.{date_str[4:6]}.{date_str[6:]})"

        recipients = default_recipients or ["admin@skenmove.com"]

        try:
            message = create_email(sender, recipients, subject, html)
            service.users().messages().send(userId="me", body=message).execute()
            send_results[country] = True
            logger.info(f"[{country}] Email sent to {len(recipients)} recipients")
        except Exception as e:
            logger.error(f"[{country}] Send failed: {e}")
            send_results[country] = False

    return {
        "send_results": send_results,
        "current_phase": "complete",
        "phase_status": {**state.get("phase_status", {}), "sending": "done"},
        "events": state.get("events", []) + [
            {"type": "phase_complete", "phase": "sending", "ts": datetime.now().isoformat(),
             "results": send_results}
        ],
    }
