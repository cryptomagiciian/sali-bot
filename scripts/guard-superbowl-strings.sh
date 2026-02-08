#!/usr/bin/env bash
set -euo pipefail

BAD=$(rg -n "Kansas City Chiefs|San Francisco 49ers|\bChiefs\b|\b49ers\b|superbowlTeams" . || true)

if [[ -n "$BAD" ]]; then
  echo "❌ Found legacy Super Bowl strings. Replace with config + formatters:"
  echo "$BAD"
  exit 1
fi

echo "✅ No legacy Super Bowl strings found."
