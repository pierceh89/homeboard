#!/usr/bin/env sh
DEBUG=${DEBUG:-false}
[ "$DEBUG" = true ] && set -x

DIR="$(dirname "$0")"
LOG_FILE="$DIR/log/dash.log"
ENV_FILE=".env"

if [ -f "$DIR/$ENV_FILE" ]; then
  set -a
  . "$DIR/$ENV_FILE"
  set +a
fi

mkdir -p "$(dirname "$LOG_FILE")"

if [ "$DEBUG" = true ]; then
  "$DIR/dash.sh"
else
  "$DIR/dash.sh" >>"$LOG_FILE" 2>&1 &
fi
