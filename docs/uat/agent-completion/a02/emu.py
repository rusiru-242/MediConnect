"""Minimal adb driver for the A01/A02 emulator checks (emulator-5554 only).

Usage (from backend/):  venv\\Scripts\\python.exe ..\\docs\\uat\\agent-completion\\a01\\emu.py <command> [args]
  focus                      print the focused window (input is refused unless MediConnect is in the foreground)
  dump                       list visible texts / content descriptions with their centre points
  tap <x> <y> | tapt <text>  tap a point, or the first element whose text/description contains <text>
  type <text> | password     type text; "password" types the synthetic UAT password from uat.env (never printed)
  key <code> | shot <name>   key event; screenshot into evidence/emulator/<name>.png
"""
import pathlib
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ADB = str(pathlib.Path.home() / "AppData/Local/Android/Sdk/platform-tools/adb.exe")
SERIAL = "emulator-5554"
PACKAGE = "com.mediconnect"
ROOT = pathlib.Path(__file__).resolve().parents[4]
OUT = pathlib.Path(__file__).resolve().parent / "evidence" / "emulator"


def adb(*args, binary=False):
    res = subprocess.run([ADB, "-s", SERIAL, *args], capture_output=True)
    return res.stdout if binary else res.stdout.decode("utf-8", "replace")


def focused():
    out = adb("shell", "dumpsys", "window")
    m = re.search(r"mCurrentFocus=.*?\s(\S+)/", out) or re.search(r"mFocusedApp=.*?\s(\S+)/", out)
    return m.group(1) if m else ""


def require_foreground():
    pkg = focused()
    if PACKAGE not in pkg:
        sys.exit(f"refused: foreground app is {pkg!r}, not MediConnect")


def nodes():
    adb("shell", "uiautomator", "dump", "/sdcard/a01_ui.xml")
    xml = adb("shell", "cat", "/sdcard/a01_ui.xml")
    xml = xml[xml.find("<?xml"):]
    rows = []
    for n in ET.fromstring(xml).iter("node"):
        label = (n.get("text") or "") or (n.get("content-desc") or "")
        b = re.findall(r"\d+", n.get("bounds") or "")
        if label and len(b) == 4:
            x1, y1, x2, y2 = map(int, b)
            rows.append((label.replace("\n", " ")[:120], (x1 + x2) // 2, (y1 + y2) // 2, n.get("class")))
    return rows


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "focus":
        print(focused())
    elif cmd == "dump":
        for label, x, y, cls in nodes():
            print(f"{x:5d},{y:5d}  {cls.split('.')[-1]:12s} {label}")
    elif cmd == "tap":
        require_foreground()
        adb("shell", "input", "tap", args[0], args[1])
    elif cmd == "tapt":
        require_foreground()
        want = " ".join(args).lower()
        for label, x, y, _ in nodes():
            if want in label.lower():
                adb("shell", "input", "tap", str(x), str(y))
                print("tapped", label[:60], x, y)
                return
        sys.exit(f"not found: {want}")
    elif cmd == "type":
        require_foreground()
        adb("shell", "input", "text", " ".join(args).replace(" ", "%s"))
    elif cmd == "password":
        require_foreground()
        env = (ROOT / "backend" / "uat.env").read_text(encoding="utf-8")
        pw = re.search(r"^UAT_PASSWORD=(.*)$", env, re.M).group(1).strip().strip("\"'")
        adb("shell", "input", "text", pw)
        print("typed synthetic UAT password (not shown)")
    elif cmd == "key":
        require_foreground()
        adb("shell", "input", "keyevent", args[0])
    elif cmd == "shot":
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"{args[0]}.png").write_bytes(adb("exec-out", "screencap", "-p", binary=True))
        print("saved", args[0])
    time.sleep(0.3)


if __name__ == "__main__":
    main()
