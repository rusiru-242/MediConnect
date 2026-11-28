"""R02 UAT helper: fill a Flutter text field on the emulator by its hint, safely.

Usage (from docs/uat/release-preparation/r02):  ..\\..\\..\\..\\backend\\venv\\Scripts\\python.exe fill.py "<hint>" "<text>"
Re-reads the live layout before tapping, refuses input unless MediConnect is in the foreground, clears the field,
types, and closes the keyboard with Back only when the keyboard is actually shown (so Back never leaves the app).
"""
import re
import subprocess
import sys
import time

import emu


def keyboard_shown() -> bool:
    out = emu.adb("shell", "dumpsys", "input_method")
    return bool(re.search(r"mInputShown=true", out))


def field_center(hint: str):
    emu.adb("shell", "uiautomator", "dump", "/sdcard/r02f.xml")
    xml = emu.adb("shell", "cat", "/sdcard/r02f.xml")
    for node in re.findall(r"<node [^>]*>", xml):
        if "EditText" in node and f'hint="{hint}"' in node:
            x1, y1, x2, y2 = map(int, re.findall(r"\d+", re.search(r'bounds="([^"]+)"', node).group(1)))
            return (x1 + x2) // 2, (y1 + y2) // 2
    sys.exit(f"field not found: {hint}")


def main():
    hint, text = sys.argv[1], sys.argv[2]
    emu.require_foreground()
    if keyboard_shown():
        emu.adb("shell", "input", "keyevent", "KEYCODE_BACK")
        time.sleep(0.6)
    x, y = field_center(hint)
    emu.adb("shell", "input", "tap", str(x), str(y))
    time.sleep(0.6)
    emu.adb("shell", "input", "keyevent", "KEYCODE_MOVE_END")
    emu.adb("shell", "input", "keyevent", *(["KEYCODE_DEL"] * 50))
    emu.adb("shell", "input", "text", text.replace(" ", "%s"))
    time.sleep(0.4)
    if keyboard_shown():
        emu.adb("shell", "input", "keyevent", "KEYCODE_BACK")
        time.sleep(0.6)
    print("filled", hint)


if __name__ == "__main__":
    main()
