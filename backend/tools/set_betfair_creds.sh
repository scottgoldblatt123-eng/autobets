#!/bin/bash
# Prompts for Betfair credentials and writes them to the protected env file. Nothing is echoed or logged.
F=/opt/autobets/secrets/betfair.env
read -r -p "App key: " K
read -r -p "Username: " U
read -r -s -p "Password (hidden): " P; echo
echo "Lengths -> key: ${#K}  username: ${#U}  password: ${#P}"
read -r -p "Save these? (y/n) " A
if [ "$A" = "y" ]; then
  umask 077
  printf 'BETFAIR_APP_KEY=%s\nBETFAIR_USERNAME=%s\nBETFAIR_PASSWORD=%s\n' "$K" "$U" "$P" > "$F"
  chmod 600 "$F"
  echo "Saved to $F"
else
  echo "Nothing saved."
fi
