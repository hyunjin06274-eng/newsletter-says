#!/bin/bash
# Gmail 토큰을 GitHub Secret으로 등록하는 스크립트
# 사용법: bash scripts/export_gmail_token.sh
#
# 사전 조건:
# 1. gh auth login 완료
# 2. .gmail_token.json 파일 존재 (로컬에서 최소 1회 Gmail 인증 완료)
# 3. .gmail_credentials.json 파일 존재

set -e

REPO="hyunjin06274-eng/newsletter-says"

echo "=== Gmail 토큰을 GitHub Secrets로 등록합니다 ==="
echo ""

# 1. Gmail Token
TOKEN_FILE="../.gmail_token.json"
if [ ! -f "$TOKEN_FILE" ]; then
    TOKEN_FILE="../../뉴스레터 작성_24개 병렬ver/.gmail_token.json"
fi

if [ -f "$TOKEN_FILE" ]; then
    echo "✅ Gmail token 발견: $TOKEN_FILE"
    gh secret set GMAIL_TOKEN_JSON --repo "$REPO" < "$TOKEN_FILE"
    echo "   → GMAIL_TOKEN_JSON 등록 완료"
else
    echo "❌ Gmail token 파일을 찾을 수 없습니다."
    echo "   먼저 로컬에서 Gmail 인증을 실행하세요."
    exit 1
fi

# 2. Gmail Credentials
CREDS_FILE="../.gmail_credentials.json"
if [ ! -f "$CREDS_FILE" ]; then
    CREDS_FILE="../../뉴스레터 작성_24개 병렬ver/.gmail_credentials.json"
fi

if [ -f "$CREDS_FILE" ]; then
    echo "✅ Gmail credentials 발견: $CREDS_FILE"
    gh secret set GMAIL_CREDENTIALS_JSON --repo "$REPO" < "$CREDS_FILE"
    echo "   → GMAIL_CREDENTIALS_JSON 등록 완료"
fi

echo ""
echo "=== 나머지 API 키도 등록하시겠습니까? ==="
echo ""

# 3. .env에서 API 키 읽기
ENV_FILE="../.env"
if [ ! -f "$ENV_FILE" ]; then
    ENV_FILE="../../뉴스레터 작성_24개 병렬ver/.env"
fi

if [ -f "$ENV_FILE" ]; then
    while IFS='=' read -r key value; do
        # 주석 및 빈 줄 건너뛰기
        [[ "$key" =~ ^#.*$ ]] && continue
        [[ -z "$key" ]] && continue

        # API 키만 처리
        case "$key" in
            ANTHROPIC_API_KEY|GOOGLE_API_KEY|TAVILY_API_KEY)
                if [ -n "$value" ]; then
                    echo "  등록: $key"
                    echo "$value" | gh secret set "$key" --repo "$REPO"
                fi
                ;;
        esac
    done < "$ENV_FILE"
    echo "   → API 키 등록 완료"
fi

echo ""
echo "=== 완료! ==="
echo ""
echo "등록된 Secrets 확인:"
gh secret list --repo "$REPO"
echo ""
echo "이제 GitHub Actions가 맥북 없이 자동 실행됩니다."
echo "수동 실행: gh workflow run schedule.yml --repo $REPO"
