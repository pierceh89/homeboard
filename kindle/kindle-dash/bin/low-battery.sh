#!/usr/bin/env sh

battery_level_percentage=$1
DIR="$(dirname "$0")"
last_battery_report_state="$DIR/state/last_battery_report"

previous_report_timestamp=$(cat "$last_battery_report_state" 2>/dev/null || echo '-1')
now=$(date +%s)

# Default behavior: report low battery at most once every 24 hours.
if [ "$previous_report_timestamp" -eq -1 ] ||
  [ $((now - previous_report_timestamp)) -gt 86400 ]; then
  # Customize this hook (for example: curl/webhook/slack notification).
  echo "[$(date -u)] Reporting low battery: ${battery_level_percentage}%"
  echo "$now" >"$last_battery_report_state"
  MESSAGE="[KINDLE] Reporting low battery: ${battery_level_percentage}%"
  if [ -n "$DISCORD_WEBHOOK_URL" ]; then
    curl -H "Content-Type: application/json" \
      -d "$(printf '{"content": "%s"}' "$MESSAGE")" \
      "$DISCORD_WEBHOOK_URL"
  else
    echo "[$(date -u)] DISCORD_WEBHOOK_URL is not set; skipping low battery notification"
  fi
fi
