#!/usr/bin/env sh

# In case a refresh is mid-run, stop any script.sh that's still executing
pkill -f dash.sh

# Re-enable the screensaver so the lock button works normally again
# lipc-set-prop com.lab126.powerd preventScreenSaver 0

# Restart the Kindle UI so the home screen and menus work again (no-op if we never stopped them)
# /sbin/start framework   2>/dev/null || true
# /sbin/start lab126_gui  2>/dev/null || true