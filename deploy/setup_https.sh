#!/bin/bash
# Run ONCE on the server (as root). Puts AutoBets behind HTTPS so you can open it from any device
# without an SSH tunnel. The app itself stays on 127.0.0.1:8000; only Caddy faces the internet.
# Uses a free sslip.io hostname (no domain needed) and an automatic Let's Encrypt certificate.
set -euo pipefail
IP="${1:-159.65.20.243}"
HOST="${IP//./-}.sslip.io"
if ! command -v caddy >/dev/null; then
  apt-get update -qq
  apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https curl gpg
  curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/gpg.key | gpg --dearmor -o /usr/share/keyrings/caddy.gpg
  curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt | sed 's#^deb #deb [signed-by=/usr/share/keyrings/caddy.gpg] #' > /etc/apt/sources.list.d/caddy.list
  apt-get update -qq && apt-get install -y -qq caddy
fi
cat > /etc/caddy/Caddyfile <<CADDY
$HOST {
    encode gzip
    reverse_proxy 127.0.0.1:8000
}
CADDY
if command -v ufw >/dev/null && ufw status | grep -q active; then ufw allow 80/tcp; ufw allow 443/tcp; fi
systemctl enable --now caddy; systemctl reload caddy
echo; echo "Open:  https://$HOST/"
echo "If it does not load in a minute: DigitalOcean > Networking > Firewalls must allow inbound 80 and 443."
echo "Practice mode asks for your AUTOBETS_TOKEN (grep AUTOBETS_TOKEN /opt/autobets/secrets/betfair.env)."
