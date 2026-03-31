#!/usr/bin/env sh

DEBUG=${DEBUG:-false}
DIR="$(dirname "$0")"
SCREEN_URL="http://192.168.123.181:8000/kindle-image"
REFRESH_SCHEDULE="*/30 6-19 * * *"
TIMEZONE="Asia/Seoul"
FULL_DISPLAY_REFRESH_RATE=${FULL_DISPLAY_REFRESH_RATE:-4}
LOW_BATTERY_REPORTING=${LOW_BATTERY_REPORTING:-false}
LOW_BATTERY_THRESHOLD_PERCENT=${LOW_BATTERY_THRESHOLD_PERCENT:-10}
LOW_BATTERY_CMD=${LOW_BATTERY_CMD:-"$DIR/low-battery.sh"}
num_refresh=0


log() {
    echo "[$(date '+%Y-%m-%d %I:%M %p')] $1"
}

init() {
  if [ -z "$TIMEZONE" ] || [ -z "$REFRESH_SCHEDULE" ]; then
    log "Missing required configuration."
    log "Timezone: ${TIMEZONE:-(not set)}."
    log "Schedule: ${REFRESH_SCHEDULE:-(not set)}."
    exit 1
  fi

  log "Starting dashboard with $REFRESH_SCHEDULE refresh..."

  #stop framework
  if [ "$ISKINDLE4NT" = true ]; then
      /etc/init.d/framework stop #kindle NT4 code
  else
      stop framework
      stop lab126_gui #code for kindle paperwhite3
  fi

  initctl stop webreader >/dev/null 2>&1
  echo powersave >/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
  lipc-set-prop com.lab126.powerd preventScreenSaver 1
  mkdir -p "$DIR/state"
}

refresh_dashboard() {
  log "Refreshing dashboard"

  curl -k "$SCREEN_URL" -o "$DIR/screen.png"
  fetch_status=$?
  if [ "$fetch_status" -ne 0 ]; then
    log "Not updating screen, fetch failed with exit code $fetch_status"
    return 1
  fi

  if [ "$num_refresh" -eq "$FULL_DISPLAY_REFRESH_RATE" ]; then
    num_refresh=0
    log "Full screen refresh"
    eips -c
    eips -f -g "$DIR/screen.png" -w gc16
    # eips -f -g "$DIR/screen.png" -x 0 -y 35 -w gc16
  else
    log "Partial screen refresh"
    eips -g "$DIR/screen.png" -w gc16
    # eips -g "$DIR/screen.png" -x 0 -y 35 -w gc16
  fi
  num_refresh=$((num_refresh + 1))

  # Draw date/time and battery at top (eips can't print %, so we strip it from gasgauge-info -c)
  # eips 1 1 "$(date '+%Y-%m-%d %I:%M %p') - wifi $(cat /sys/class/net/wlan0/operstate 2>/dev/null || echo '?') - battery: $(gasgauge-info -c 2>/dev/null | sed 's/%//g' || echo '?')"
}

log_battery_stats() {
  battery_level=$(gasgauge-info -c)
  battery_mah=$(gasgauge-info -m)
  log "Battery level: $battery_level, $battery_mah"

  if [ "$LOW_BATTERY_REPORTING" = true ]; then
    battery_level_numeric=${battery_level%?}
    if [ "$battery_level_numeric" -le "$LOW_BATTERY_THRESHOLD_PERCENT" ]; then
      if [ -x "$LOW_BATTERY_CMD" ]; then
        "$LOW_BATTERY_CMD" "$battery_level_numeric"
      else
        log "Low battery hook is not executable: $LOW_BATTERY_CMD"
      fi
    fi
  fi
}

rtc_sleep() {
  duration=$1

  if [ "$DEBUG" = true ]; then
    sleep "$duration"
  else
    rtcwake -d /dev/rtc1 -m no -s "$duration"
    echo "mem" >/sys/power/state
  fi
}

main_loop() {
  while true; do
    log "Woke up, refreshing dashboard"
    log_battery_stats

    next_wakeup_secs=$("$DIR/next-wakeup" --schedule="$REFRESH_SCHEDULE" --timezone="$TIMEZONE")

    refresh_dashboard

    # take a bit of time before going to sleep, so this process can be aborted
    sleep 10

    log "Going to sleep, next wakeup in ${next_wakeup_secs}s"
    rtc_sleep "$next_wakeup_secs"
  done
}

init
main_loop
