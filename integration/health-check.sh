#!/usr/bin/env bash
# health-check.sh — Verifica el estado de todos los servicios NEXT
set -euo pipefail

API_URL="${NEXT_API_URL:-http://localhost:8000}"
DASH_URL="${NEXT_DASH_URL:-http://localhost:8501}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5433}"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0

check() {
    local name="$1" url="$2"
    printf "  %-30s" "$name"
    if curl -sf -o /dev/null -m 5 "$url"; then
        echo -e "${GREEN}✅ OK${NC}"
        ((PASS++))
    else
        echo -e "${RED}❌ FAIL${NC}"
        ((FAIL++))
    fi
}

echo "========================================"
echo "  NEXT Health Check — $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "========================================"
echo ""

# 1. PostgreSQL
printf "  %-30s" "PostgreSQL ($DB_HOST:$DB_PORT)"
if pg_isready -h "$DB_HOST" -p "$DB_PORT" -q 2>/dev/null; then
    echo -e "${GREEN}✅ OK${NC}"
    ((PASS++))
else
    echo -e "${RED}❌ FAIL${NC}"
    ((FAIL++))
fi

# 2. API endpoints
check "API /health"          "$API_URL/health"
check "API /api/v1/matches"  "$API_URL/api/v1/matches?limit=1"
check "API /api/v1/predict"  "$API_URL/api/v1/predict"  # Puede fallar sin body
check "API /docs"            "$API_URL/docs"

# 3. Dashboard
check "Dashboard /"                "$DASH_URL"
check "Dashboard /_stcore/health"  "$DASH_URL/_stcore/health"

# 4. DNS / dominios externos
echo ""
echo "--- Dominios externos ---"
check "api.next.thefuckinggoat.cloud"    "https://api.next.thefuckinggoat.cloud/health"
check "next.thefuckinggoat.cloud"        "https://next.thefuckinggoat.cloud/_stcore/health"

echo ""
echo "========================================"
echo -e "  Total: ${GREEN}$PASS OK${NC} / ${RED}$FAIL FAIL${NC}"
echo "========================================"

exit $FAIL
