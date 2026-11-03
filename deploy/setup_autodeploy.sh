#!/bin/bash
# Run ONCE on the server. Creates a deploy key that can do nothing except run deploy/deploy.sh, and prints what to paste into GitHub.
set -euo pipefail
KEY="$HOME/.ssh/autobets_deploy"; IP="${1:-159.65.20.243}"
chmod +x /opt/autobets/app/deploy/deploy.sh
mkdir -p "$HOME/.ssh"; chmod 700 "$HOME/.ssh"; touch "$HOME/.ssh/authorized_keys"; chmod 600 "$HOME/.ssh/authorized_keys"
[ -f "$KEY" ] || ssh-keygen -q -t ed25519 -N "" -C autobets-deploy -f "$KEY"
grep -q 'autobets-deploy' "$HOME/.ssh/authorized_keys" || echo "command=\"/opt/autobets/app/deploy/deploy.sh\",restrict $(cat "$KEY.pub")" >> "$HOME/.ssh/authorized_keys"
echo; echo "Add these 4 secrets in GitHub (repo > Settings > Secrets and variables > Actions > New repository secret):"
echo "  DEPLOY_HOST  = $IP"; echo "  DEPLOY_USER  = $(whoami)"
echo; echo "  DEPLOY_KEY   = everything between the two lines below, including the BEGIN and END lines"; echo "-----8<-----"; cat "$KEY"; echo "----->8-----"
echo; echo "  DEPLOY_KNOWN_HOSTS = the line below"; ssh-keyscan -t ed25519 "$IP" 2>/dev/null
echo; echo "When the secrets are saved, remove the private key from the server:  shred -u $KEY"
