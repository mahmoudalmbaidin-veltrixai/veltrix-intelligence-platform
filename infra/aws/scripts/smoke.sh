#!/usr/bin/env bash
set -euo pipefail

readonly CERTIFIED_SHA="4e97591845a93037d6e54b0237bcb3208d1b2696"

[[ $# -eq 3 ]] || {
  echo "usage: smoke.sh ENV APP_URL API_URL" >&2
  exit 64
}

environment="$1"
app_url="${2%/}"
api_url="${3%/}"

[[ "$environment" == "staging" || "$environment" == "production" ]] || {
  echo "ENV must be staging or production" >&2
  exit 64
}

curl --fail --silent --show-error --location "$app_url/healthz" | grep -q '^ok'
curl --fail --silent --show-error "$api_url/health" | jq -e '.status == "healthy"' >/dev/null
curl --fail --silent --show-error "$api_url/ready" | jq -e '
  .status == "ready"
  and .checks.database.status == "healthy"
  and .checks.redis.status == "healthy"
' >/dev/null
curl --fail --silent --show-error "$api_url/api/v1/version" | jq -e \
  --arg sha "$CERTIFIED_SHA" \
  '.environment != "development" and .commit_sha == $sha' >/dev/null

headers="$(mktemp)"
curl --silent --show-error --head "$api_url/health" > "$headers"
if [[ "$environment" == "production" ]]; then
  grep -qi '^strict-transport-security:' "$headers"
fi
grep -qi '^x-content-type-options: nosniff' "$headers"
rm -f "$headers"

http_url="${app_url/https:\/\//http://}"
redirect="$(curl --silent --show-error --output /dev/null --write-out '%{http_code} %{redirect_url}' "$http_url/")"
[[ "$redirect" == 301\ https://* || "$redirect" == 302\ https://* ]]

echo "Infrastructure smoke PASS for $CERTIFIED_SHA"
