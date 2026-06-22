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
    "GCC": "GCC(걸프협력회의)",
    "CN": "중국", "US": "미국", "IN": "인도", "JP": "일본",
    "AE": "UAE", "SA": "사우디아라비아", "OM": "오만", "EG": "이집트",
    "MY": "말레이시아", "KH": "캄보디아", "LA": "라오스",
    "CL": "칠레", "AU": "호주", "IL": "이스라엘", "MN": "몽골",
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


def create_email(sender: str, to: list[str], subject: str, html_body: str, cc: list[str] | None = None) -> dict:
    """Create a Gmail-compatible email message with optional CC."""
    msg = MIMEMultipart("alternative")
    msg["From"] = sender
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
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

    # Load recipients — sources are MERGED (not mutually exclusive):
    # 1. settings.country_recipients (primary: TO/CC per country, set via UI)
    # 2. recipients table (legacy: additional global TO, always included)
    # 3. DEFAULT_RECIPIENTS env var (fallback if both above are empty)
    global_to: list[str] = []
    global_cc: list[str] = []
    country_to: dict[str, list[str]] = {}
    country_cc: dict[str, list[str]] = {}

    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_KEY", "")

    if supabase_url and supabase_key:
        import requests as _req
        headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}

        # 1순위: settings.country_recipients — UI에서 설정한 TO/CC (주 소스)
        try:
            resp = _req.get(
                f"{supabase_url}/rest/v1/settings?order=id.desc&limit=1&select=country_recipients",
                headers=headers,
                timeout=10,
            )
            if resp.ok and resp.json():
                for cr in resp.json()[0].get("country_recipients", []):
                    # 신규 {to, cc} 포맷 + 구 {recipients} 포맷 호환
                    to_list = cr.get("to", cr.get("recipients", []))
                    cc_list = cr.get("cc", [])
                    if cr.get("country") == "ALL":
                        global_to = list(to_list)
                        global_cc = list(cc_list)
                    else:
                        country_to[cr["country"]] = list(to_list)
                        country_cc[cr["country"]] = list(cc_list)
                logger.info(f"[settings] global_to={global_to}, global_cc={global_cc}, countries={list(country_to.keys())}")
                print(f"[settings] global_to={global_to}, global_cc={global_cc}, countries={list(country_to.keys())}", flush=True)
        except Exception as e:
            logger.warning(f"Failed to load from settings: {e}")

        # 2순위: recipients 테이블 — global_to에 병합 (기존 데이터 보존)
        try:
            resp = _req.get(
                f"{supabase_url}/rest/v1/recipients?is_active=eq.true&select=email,country",
                headers=headers,
                timeout=10,
            )
            if resp.ok and resp.json():
                for row in resp.json():
                    raw_email = row.get("email", "")
                    c = row.get("country", "ALL")
                    # JSON 배열 문자열로 저장된 경우 파싱
                    if isinstance(raw_email, str) and raw_email.startswith("["):
                        try:
                            emails = json.loads(raw_email)
                        except Exception:
                            emails = [raw_email]
                    else:
                        emails = [raw_email]
                    for email in emails:
                        email = str(email).strip()
                        if not email or "@" not in email:
                            continue
                        if c == "ALL":
                            if email not in global_to:
                                global_to.append(email)
                        else:
                            lst = country_to.setdefault(c, [])
                            if email not in lst:
                                lst.append(email)
                logger.info(f"[recipients table merged] global_to={global_to}, extras={list(country_to.keys())}")
                print(f"[recipients table merged] global_to={global_to}, extras={list(country_to.keys())}", flush=True)
        except Exception as e:
            logger.warning(f"Failed to load from recipients table: {e}")

    # 3순위: DEFAULT_RECIPIENTS 환경변수 (두 소스 모두 비어있을 때만)
    if not global_to and not country_to:
        env_recip = os.environ.get("DEFAULT_RECIPIENTS", "").split(",")
        global_to = [r.strip() for r in env_recip if r.strip()]
        if global_to:
            logger.info(f"[env fallback] DEFAULT_RECIPIENTS={global_to}")
            print(f"[env fallback] DEFAULT_RECIPIENTS={global_to}", flush=True)

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

        # Merge global + country-specific TO/CC
        to_list = list(global_to) + list(country_to.get(country, []))
        cc_list = list(global_cc) + list(country_cc.get(country, []))
        # Dedupe; CC must not overlap with TO
        to_list = list(dict.fromkeys(r for r in to_list if r))
        cc_list = list(dict.fromkeys(r for r in cc_list if r and r not in to_list))

        if not to_list:
            logger.warning(f"[{country}] No TO recipients configured, skipping")
            send_results[country] = False
            continue

        try:
            message = create_email(sender, to_list, subject, html, cc=cc_list or None)
            await asyncio.to_thread(
                service.users().messages().send(userId="me", body=message).execute
            )
            send_results[country] = True
            logger.info(f"[{country}] Email sent to={to_list} cc={cc_list}")
            print(f"[{country}] Email sent to={to_list} cc={cc_list}", flush=True)
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
