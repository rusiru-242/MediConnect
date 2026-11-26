"""Encrypt, rotate or decrypt the application-managed upload files in place (Phase 05, B8).

    python -m scripts.encrypt_existing_documents                 # dry run: counts only (default)
    python -m scripts.encrypt_existing_documents --apply         # encrypt legacy plaintext files
    python -m scripts.encrypt_existing_documents --rotate        # re-encrypt files not using the current key
    python -m scripts.encrypt_existing_documents --revert        # decrypt back to plaintext (rollback)
    python -m scripts.encrypt_existing_documents --generate-key uat-2   # print a new key entry (operator use)

Scope: backend/uploads/{doctor_verification,medical_documents,companion_images} (or --root). Keys are read from
DOCUMENT_ENCRYPTION_KEYS; the script never prints key material except for --generate-key.

Safety:
* each file is written to a temporary sibling and swapped in with os.replace, so an interrupted run leaves every
  file either fully old or fully new;
* the result is decrypted and compared with the original before the swap;
* it touches only files on this machine. Database metadata ("encrypted": true) is not required for reading:
  the reader recognises the container format. Production or shared storage must not be migrated without the
  owner's approval and a backup.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "uploads"
STORES = ("doctor_verification", "medical_documents", "companion_images")


def _files(root: Path):
    for store in STORES:
        base = root / store
        if base.is_dir():
            for f in sorted(base.rglob("*")):
                if f.is_file() and not f.name.endswith(".tmp-enc"):
                    yield store, base, f


def run(root: Path, mode: str) -> dict:
    from app.services import document_crypto as dc
    ring = dc.keyring()
    if mode in ("apply", "rotate", "revert") and not ring.configured:
        raise SystemExit("DOCUMENT_ENCRYPTION_KEYS is not set.")
    stats = {"mode": mode, "plaintext": 0, "encrypted": 0, "changed": 0, "failed": 0}
    for store, base, f in _files(root):
        rel = f.relative_to(base).as_posix()
        context = f"{store}/{rel}"
        blob = f.read_bytes()
        enc = dc.is_encrypted(blob)
        stats["encrypted" if enc else "plaintext"] += 1
        try:
            if mode == "apply" and not enc:
                new = dc.encrypt(blob, context, ring)
                original = blob
            elif mode == "rotate" and enc and dc.key_id_of(blob) != ring.current:
                original = dc.decrypt(blob, context, ring)
                new = dc.encrypt(original, context, ring)
            elif mode == "revert" and enc:
                original = dc.decrypt(blob, context, ring)
                new = original
            else:
                continue
            check = dc.decrypt(new, context, ring) if dc.is_encrypted(new) else new
            if check != original:
                raise RuntimeError("verification failed")
            tmp = f.with_name(f.name + ".tmp-enc")
            tmp.write_bytes(new)
            os.replace(tmp, f)
            stats["changed"] += 1
        except Exception as exc:  # report and continue; the original file is untouched
            stats["failed"] += 1
            print(f"FAILED {context}: {type(exc).__name__}", file=sys.stderr)
    return stats


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--apply", action="store_true")
    group.add_argument("--rotate", action="store_true")
    group.add_argument("--revert", action="store_true")
    group.add_argument("--generate-key", metavar="KEY_ID")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    if args.generate_key:
        from app.services.document_crypto import generate_key_entry
        print(generate_key_entry(args.generate_key))
        return 0
    mode = "apply" if args.apply else "rotate" if args.rotate else "revert" if args.revert else "dry-run"
    print(run(args.root, mode))
    return 0


if __name__ == "__main__":
    sys.exit(main())
