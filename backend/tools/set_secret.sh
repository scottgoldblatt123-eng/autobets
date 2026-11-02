#!/bin/bash
# Usage: bash backend/tools/set_secret.sh NAME
# Prompts (hidden) for a value and stores it as NAME=value in /opt/autobets/secrets/NAME.env (mode 600).
# Example: bash backend/tools/set_secret.sh TENNIS_API_KEY
set -e
NAME="$1"
[ -z "$NAME" ] && { echo "Usage: set_secret.sh NAME"; exit 1; }
FILE="/opt/autobets/secrets/$(echo "$NAME" | tr 'A-Z' 'a-z').env"
read -r -s -p "Value for $NAME (hidden): " V; echo
echo "Length: ${#V}"
read -r -p "Save? (y/n) " A
if [ "$A" = "y" ]; then
  umask 077
  printf '%s=%s\n' "$NAME" "$V" > "$FILE"
  chmod 600 "$FILE"
  echo "Saved to $FILE"
else
  echo "Nothing saved."
fi
