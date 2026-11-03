#!/bin/bash
# Auto-deploy for the practice server. Run by GitHub Actions over a restricted SSH key (forced command), or by hand.
# Pulls the latest main (fast-forward only) and restarts the API only when nothing would be lost by doing so.
# Wrapped in a function so git can safely replace this file while it runs.
main() {
  set -uo pipefail
  APP="${APP_DIR:-/opt/autobets/app}"
  ENVF="${API_ENV:-/opt/autobets/secrets/api.env}"
  LOG="${DEPLOY_LOG:-/opt/autobets/data/deploy.log}"
  RESTART="${RESTART_CMD:-sudo systemctl restart autobets-api}"
  BUSY_URL="${BUSY_URL:-http://127.0.0.1:8000/api/busy}"
  PEND="${PENDING_FLAG:-/opt/autobets/data/restart_pending}"
  say() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }

  cd "$APP" || { say "deploy: cannot cd to $APP"; return 1; }
  git fetch -q origin main || { say "deploy: git fetch failed"; return 1; }
  old=$(git rev-parse HEAD); new=$(git rev-parse origin/main)
  if [ "$old" = "$new" ] && [ ! -e "$PEND" ]; then say "deploy: already up to date (${new:0:7})"; return 0; fi
  if [ "$old" != "$new" ]; then
    git merge --ff-only -q origin/main || { say "deploy: cannot fast-forward (local changes on the server?) — not deployed"; return 1; }
    say "deploy: updated ${old:0:7} -> ${new:0:7}"
  else
    say "deploy: retrying a restart that was held back earlier"
  fi
  if git diff --name-only "$old" "$new" | grep -q '^backend/pyproject.toml$'; then say "deploy: NOTE backend dependencies changed — run pip install on the server"; fi

  if grep -qs '^AUTOBETS_MODE=live' "$ENVF"; then say "deploy: live mode — code updated, NOT restarted (restart by hand)"; rm -f "$PEND"; return 0; fi
  token=$(grep -s '^AUTOBETS_TOKEN=' "$ENVF" | head -1 | cut -d= -f2- | tr -d "\"'")
  busy=$(curl -fsS -m 5 -H "X-Auth: $token" "$BUSY_URL" 2>/dev/null) || busy=""
  if [ -n "$busy" ] && ! echo "$busy" | grep -Eq '"triggers": *0.*"open_orders": *0'; then
    say "deploy: code updated but NOT restarted — stops or open orders are active ($busy). It will restart on the next deploy once clear, or run deploy.sh by hand"
    touch "$PEND"; return 0
  fi
  $RESTART && { rm -f "$PEND"; say "deploy: restarted autobets-api"; } || { say "deploy: restart FAILED"; return 1; }
}
main "$@"
exit $?
