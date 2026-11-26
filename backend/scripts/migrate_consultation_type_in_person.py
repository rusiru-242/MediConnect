"""Reversible migration: historical VIDEO/AUDIO care-plan consultation types -> IN_PERSON (Phase 02).

NOT run automatically and NOT approved for production. Default mode is a dry run that only counts.
  python scripts/migrate_consultation_type_in_person.py               # dry run (counts only)
  python scripts/migrate_consultation_type_in_person.py --apply       # sets IN_PERSON, keeps the old value
  python scripts/migrate_consultation_type_in_person.py --revert      # restores the old value

--apply stores the previous value in legacyConsultationType and records migratedAt, so --revert is exact.
Refuses to run unless MONGODB_URI points at localhost, or --allow-remote is given explicitly after owner approval.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlsplit

from pymongo import MongoClient

FIELD = "recommendedConsultationType"
MARK = "phase02_in_person_only"


def run(db, mode: str) -> dict:
    plans = db["care_plans"]
    if mode == "revert":
        query = {"legacyConsultationType": {"$exists": True}, "consultationTypeMigration": MARK}
        count = plans.count_documents(query)
        for doc in plans.find(query, {"legacyConsultationType": 1}):
            plans.update_one({"_id": doc["_id"]}, {
                "$set": {FIELD: doc["legacyConsultationType"]},
                "$unset": {"legacyConsultationType": "", "consultationTypeMigration": "", "consultationTypeMigratedAt": ""},
            })
        return {"mode": mode, "reverted": count}
    query = {FIELD: {"$nin": ["IN_PERSON", None]}}
    count = plans.count_documents(query)
    if mode == "apply":
        now = datetime.now(timezone.utc)
        for doc in plans.find(query, {FIELD: 1}):
            plans.update_one({"_id": doc["_id"], FIELD: doc[FIELD]}, {"$set": {
                FIELD: "IN_PERSON", "legacyConsultationType": doc[FIELD],
                "consultationTypeMigration": MARK, "consultationTypeMigratedAt": now,
            }})
    return {"mode": mode, "matching": count}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--revert", action="store_true")
    parser.add_argument("--allow-remote", action="store_true")
    args = parser.parse_args()
    uri = os.environ.get("MONGODB_URI", "")
    name = os.environ.get("DATABASE_NAME", "")
    if not uri or not name:
        sys.exit("Set MONGODB_URI and DATABASE_NAME explicitly.")
    from app.config.db_safety import is_local_mongodb_uri  # parses every host (Phase 05; was urlsplit hostname)
    if not is_local_mongodb_uri(uri) and not args.allow_remote:
        sys.exit("Refusing a non-local database without --allow-remote (requires owner approval).")
    mode = "revert" if args.revert else "apply" if args.apply else "dry-run"
    print(run(MongoClient(uri)[name], mode))
    return 0


if __name__ == "__main__":
    sys.exit(main())
