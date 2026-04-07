"""Phase 4: Gmail API sending — supports both local file and env-based tokens."""

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
    """Build Gmail API service.

    Token resolution order:
    1. GMAIL_TOKEN_JSON env var (for GitHub Actions — token content as string)
    2. GMAIL_CREDENTIALS_JSON env var (for GitHub Actions — credentials content)
    3. Local file: .gmail_token.json / .gmail_credentials.json
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
    creds = None

    # --- Option 1: Token from environment variable (GitHub Actions) ---
    token_json_env = os.environ.get("GMAIL_TOKEN_JSON", "")
    if token_json_env:
        logger.info("Using Gmail token from GMAIL_TOKEN_JSON env var")
        token_data = json.loads(token_json_env)
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Update the env var with refreshed token (for logging)
            logger.info("Gmail token refreshed successfully")

        return build("gmail", "v1", credentials=creds)

    # --- Option 2: Token from local file (local development) ---
    token_path = Path(os.environ.get("GMAIL_TOKEN_FILE", ".gmail_token.json"))
    creds_path = Path(os.environ.get("GMAIL_CREDENTIALS_FILE", ".gmail_credentials.json"))

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # --- Option 3: Credentials from env var ---
            creds_json_env = os.environ.get("GMAIL_CREDENTIALS_JSON", "")
            if creds_json_env:
                import tempfile
                with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                    f.write(creds_json_env)
                    tmp_path = f.name
                flow = InstalledAppFlow.from_client_secrets_file(tmp_path, SCOPES)
                os.unlink(tmp_path)
            elif creds_path.exists():
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            else:
                raise FileNotFoundError(
                    "Gmail credentials not found. Set GMAIL_TOKEN_JSON env var "
                    "or provide .gmail_credentials.json file."
                )
            creds = flow.run_local_server(port=0)

        # Save refreshed token locally
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
    import asyncio

    newsletters = state.get("newsletters", {})
    date_str = state.get("date_str", datetime.now().strftime("%Y%m%d"))
    sender = os.environ.get("GMAIL_SENDER", "skenbizst@gmail.com")
    send_results: dict[str, bool] = {}

    # Load recipients from Supabase Settings
    global_recipients = []
    country_extra: dict[str, list[str]] = {}
    try:
        import requests as _req
        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_KEY", "")
        if supabase_url and supabase_key:
            resp = _req.get(
                f"{supabase_url}/rest/v1/settings?order=id.desc&limit=1&select=country_recipients",
                headers={"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"},
                timeout=10,
            )
            if resp.ok and resp.json():
                for cr in resp.json()[0].get("country_recipients", []):
                    if cr.get("country") == "ALL":
                        global_recipients = cr.get("recipients", [])
                    else:
                        country_extra[cr["country"]] = cr.get("recipients", [])
                logger.info(f"Loaded recipients: global={global_recipients}, extras={list(country_extra.keys())}")
                print(f"Loaded recipients: global={global_recipients}, extras={list(country_extra.keys())}", flush=True)
    except Exception as e:
        logger.warning(f"Failed to load recipients from Supabase: {e}")

    # Fallback to env
    if not global_recipients:
        env_recip = os.environ.get("DEFAULT_RECIPIENTS", "").split(",")
        global_recipients = [r.strip() for r in env_recip if r.strip()]

    try:
        service = await asyncio.to_thread(get_gmail_service)
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
        subject = f"{country_name} 윤활유 시장 뉴스레터 ({date_str[:4]}.{date_str[4:6]}.{date_str[6:]})"

        # Merge global + country-specific recipients
        recipients = list(global_recipients)
        if country in country_extra:
            recipients.extend(country_extra[country])
        # Dedupe
        recipients = list(dict.fromkeys(r for r in recipients if r))

        if not recipients:
            logger.warning(f"[{country}] No recipients configured, skipping")
            send_results[country] = False
            continue

        try:
            message = create_email(sender, recipients, subject, html)
            await asyncio.to_thread(
                service.users().messages().send(userId="me", body=message).execute
            )
            send_results[country] = True
            logger.info(f"[{country}] Email sent to {recipients}")
            print(f"[{country}] Email sent to {recipients}", flush=True)
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
