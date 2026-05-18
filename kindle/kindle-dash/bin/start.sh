#!/usr/bin/env sh
DEBUG=${DEBUG:-false}
[ "$DEBUG" = true ] && set -x

DIR="$(dirname "$0")"
LOG_FILE="$DIR/log/dash.log"
source $DIR/env.sh

mkdir -p "$(dirname "$LOG_FILE")"

if [ "$DEBUG" = true ]; then
  "$DIR/dash.sh"
else
  "$DIR/dash.sh" >>"$LOG_FILE" 2>&1 &
fi
