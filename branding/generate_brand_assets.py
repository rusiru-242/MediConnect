"""Generate every MediConnect brand asset from the single source logo (R01).

Usage (repository root, any Python with Pillow + numpy):
    python branding/generate_brand_assets.py

Source of truth: branding/source/mediconnect_logo_source.png (the owner-supplied horizontal logo, RGBA, transparent
background). Nothing is redrawn: every variant is a crop, a resize, a padding onto a canvas or (dark full logo only) a
recolour of the navy wordmark pixels to white so the wordmark stays readable on dark backgrounds. Aspect ratios are
always preserved (no stretching), and no effects are added.

The symbol-only variant is the heart + ECG + cross + orbit, cropped left of the vertical divider, so it never repeats
the "MediConnect" wordmark when placed beside existing title text.
"""
import json
import pathlib

import numpy as np
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "branding" / "source" / "mediconnect_logo_source.png"
EXPORTS = ROOT / "branding" / "exports"
MOBILE = ROOT / "mobile"
RES = MOBILE / "android" / "app" / "src" / "main" / "res"
IOS = MOBILE / "ios" / "Runner" / "Assets.xcassets"
ADMIN = ROOT / "admin-web"

WHITE = (255, 255, 255, 255)
DARK_BG = (15, 23, 42, 255)  # AppTheme.darkBackground / Tailwind slate-900
DIVIDER_X = 740  # the vertical divider sits at x 751-758; the symbol ends at x 720
ALPHA_MIN = 8

written = []


def trim(im):
    a = np.asarray(im)[:, :, 3] > ALPHA_MIN
    ys, xs = np.where(a.any(axis=1))[0], np.where(a.any(axis=0))[0]
    return im.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))


def fit(im, max_w, max_h):
    """Resize preserving aspect ratio so that the image fits inside max_w x max_h."""
    s = min(max_w / im.width, max_h / im.height)
    return im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)


def canvas(sym, size, scale, bg=None):
    """Square canvas of `size` px with the symbol centred, its width = scale * size (height follows the ratio)."""
    c = Image.new("RGBA", (size, size), bg or (0, 0, 0, 0))
    s = fit(sym, round(size * scale), round(size * scale))
    c.alpha_composite(s, ((size - s.width) // 2, (size - s.height) // 2))
    return c


def circle_canvas(sym, size, diameter_frac):
    """Square transparent canvas; the symbol's bounding box (diagonal) fits a centred circle of the given diameter."""
    d = size * diameter_frac
    diag = (sym.width ** 2 + sym.height ** 2) ** 0.5
    s = sym.resize((round(sym.width * d / diag), round(sym.height * d / diag)), Image.LANCZOS)
    c = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    c.alpha_composite(s, ((size - s.width) // 2, (size - s.height) // 2))
    return c


def save(im, path, mode="RGBA", **kw):
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode == "RGB":
        flat = Image.new("RGBA", im.size, WHITE)
        flat.alpha_composite(im)
        im = flat.convert("RGB")
    im.save(path, optimize=True, **kw)
    written.append((path.relative_to(ROOT).as_posix(), im.size, path.stat().st_size))


def monochrome(im):
    """Single-colour silhouette (white, original alpha) for Android 13+ themed icons."""
    a = np.asarray(im).copy()
    a[:, :, :3] = 255
    return Image.fromarray(a)


def dark_wordmark(full, wordmark_x):
    """Recolour the navy wordmark/tagline pixels (right of the divider) to near-white; teal and the symbol are kept."""
    a = np.asarray(full).astype(np.float32).copy()
    rgb = a[:, :, :3]
    lum = 0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]
    navy = (lum < 70) & (rgb[:, :, 2] > rgb[:, :, 1])  # deep navy blue; the teal "Connect" is far brighter
    mask = navy.copy()
    mask[:, :wordmark_x] = False
    a[mask, 0], a[mask, 1], a[mask, 2] = 241, 245, 249  # slate-100
    return Image.fromarray(a.clip(0, 255).astype(np.uint8))


def main():
    src = Image.open(SRC).convert("RGBA")
    full = trim(src)
    offset_x = int(np.where((np.asarray(src)[:, :, 3] > ALPHA_MIN).any(axis=0))[0].min())
    sym = trim(src.crop((0, 0, DIVIDER_X, src.height)))

    # Master exports (documentation and future use)
    save(sym, EXPORTS / "mediconnect_symbol.png")
    save(full, EXPORTS / "mediconnect_logo_full_light.png")
    save(dark_wordmark(full, DIVIDER_X - offset_x), EXPORTS / "mediconnect_logo_full_dark.png")
    save(canvas(sym, 1024, 0.72, WHITE), EXPORTS / "mediconnect_app_icon_1024.png", mode="RGB")
    for name, bg in (("light", WHITE), ("dark", DARK_BG)):
        prev = Image.new("RGBA", (full.width + 120, full.height + 120), bg)
        variant = full if name == "light" else dark_wordmark(full, DIVIDER_X - offset_x)
        prev.alpha_composite(variant, (60, 60))
        save(fit(prev, 1200, 600), EXPORTS / f"preview_full_on_{name}.png", mode="RGB")

    # Flutter in-app symbol (largest use is 88 dp; 3.0x/4.0x density variants keep it sharp)
    save(fit(sym, 264, 264), MOBILE / "assets" / "branding" / "mediconnect_symbol.png")
    save(fit(sym, 396, 396), MOBILE / "assets" / "branding" / "3.0x" / "mediconnect_symbol.png")
    save(sym, MOBILE / "assets" / "branding" / "4.0x" / "mediconnect_symbol.png")

    # Android launcher: legacy square icons (white rounded background) + adaptive icon layers (API 26+)
    densities = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}
    for d, m in densities.items():
        n = round(48 * m)
        bg = Image.new("RGBA", (n, n), (0, 0, 0, 0))
        tile = Image.new("L", (n * 4, n * 4), 0)
        ImageDraw.Draw(tile).rounded_rectangle((0, 0, n * 4 - 1, n * 4 - 1), radius=n * 4 * 0.22, fill=255)
        bg.paste(Image.new("RGBA", (n, n), WHITE), (0, 0), tile.resize((n, n), Image.LANCZOS))
        s = fit(sym, round(n * 0.74), round(n * 0.74))
        bg.alpha_composite(s, ((n - s.width) // 2, (n - s.height) // 2))
        save(bg, RES / f"mipmap-{d}" / "ic_launcher.png")
        f = round(108 * m)
        # 108 dp canvas; launcher masks show the centre 72 dp and guarantee the centre 66 dp: fit the symbol in 64 dp.
        fg = circle_canvas(sym, f, 64 / 108)
        save(fg, RES / f"mipmap-{d}" / "ic_launcher_foreground.png")
        save(monochrome(fg), RES / f"mipmap-{d}" / "ic_launcher_monochrome.png")
        # Pre-Android-12 launch window: centred symbol drawn at its intrinsic size (112 dp wide)
        save(fit(sym, round(112 * m), round(112 * m)), RES / f"drawable-{d}" / "launch_symbol.png")

    # Android 12+ system splash icon: 288 dp square, content must fit the centre 192 dp circle.
    save(circle_canvas(sym, 864, 180 / 288), RES / "drawable-nodpi" / "splash_icon.png")

    # iOS app icons (opaque, no alpha) and launch image
    contents = json.loads((IOS / "AppIcon.appiconset" / "Contents.json").read_text(encoding="utf-8"))
    for img in contents["images"]:
        pts = float(img["size"].split("x")[0])
        px = round(pts * int(img["scale"][0]))
        save(canvas(sym, px, 0.72, WHITE), IOS / "AppIcon.appiconset" / img["filename"], mode="RGB")
    for scale, suffix in ((1, ""), (2, "@2x"), (3, "@3x")):
        save(fit(sym, 120 * scale, 120 * scale), IOS / "LaunchImage.imageset" / f"LaunchImage{suffix}.png")

    # Admin web: in-app symbol, favicons, apple touch icon
    save(fit(sym, 168, 168), ADMIN / "src" / "assets" / "brand" / "mediconnect-symbol.png")
    for n in (16, 32):
        save(canvas(sym, n, 0.98), ADMIN / "public" / f"favicon-{n}x{n}.png")
    save(canvas(sym, 180, 0.74, WHITE), ADMIN / "public" / "apple-touch-icon.png", mode="RGB")
    ico = canvas(sym, 256, 0.98)
    ico_path = ADMIN / "public" / "favicon.ico"
    ico.save(ico_path, sizes=[(16, 16), (32, 32), (48, 48)])
    written.append((ico_path.relative_to(ROOT).as_posix(), (48, 48), ico_path.stat().st_size))

    for p, size, b in written:
        print(f"{p:80s} {size[0]:>4}x{size[1]:<4} {b/1024:7.1f} KB")
    print("symbol crop", sym.size, "full", full.size)


if __name__ == "__main__":
    main()
