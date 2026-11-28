#!/usr/bin/env bash
# R02 UAT helper: log a synthetic UAT account into the MediConnect emulator app from the welcome screen.
# Usage (from docs/uat/release-preparation/r02):  bash login.sh <email> [patient|doctor]
# The synthetic UAT password is typed by emu.py from backend/uat.env and never printed.
set -e
EMAIL="$1"; ROLE="${2:-patient}"
PY=../../../../backend/venv/Scripts/python.exe
ADB="$LOCALAPPDATA/Android/Sdk/platform-tools/adb.exe"
$PY emu.py tapt Login >/dev/null
sleep 2
if [ "$ROLE" = "doctor" ]; then $PY emu.py tapt Doctor >/dev/null; sleep 1; fi
# Field positions come from the live layout (they move when banners appear).
read EY PY_ < <(MSYS_NO_PATHCONV=1 "$ADB" shell uiautomator dump /sdcard/r02.xml >/dev/null; MSYS_NO_PATHCONV=1 "$ADB" shell cat /sdcard/r02.xml \
  | tr '>' '\n' | grep 'EditText' | grep -o 'bounds="\[[0-9]*,[0-9]*\]\[[0-9]*,[0-9]*\]"' \
  | sed -E 's/.*\[([0-9]+),([0-9]+)\]\[([0-9]+),([0-9]+)\].*/\2 \4/' | awk '{print int(($1+$2)/2)}' | tr '\n' ' '; echo) || true
$PY emu.py tap 720 "$EY"
"$ADB" shell input keyevent KEYCODE_MOVE_END
"$ADB" shell input keyevent $(printf 'KEYCODE_DEL %.0s' $(seq 1 50))
$PY emu.py type "$EMAIL"
$PY emu.py tap 720 "$PY_"
"$ADB" shell input keyevent KEYCODE_MOVE_END
"$ADB" shell input keyevent $(printf 'KEYCODE_DEL %.0s' $(seq 1 40))
$PY emu.py password
$PY emu.py key KEYCODE_BACK
$PY emu.py tapt Login >/dev/null
sleep 6
$PY emu.py dump | head -2
