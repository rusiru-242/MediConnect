"""Read-only audit of doctor data quality (BUG-007 duplicates, BUG-008/028 fees, BUG-006 availability).

This script NEVER modifies the database. It reports:
  1. Duplicate doctor identities (same userId / doctorId / registration number, and the same
     normalized name + specialty across different accounts).
  2. Consultation fee storage problems (missing, null, string, Decimal128, negative).
  3. Availability records whose doctorProfileId / doctorUserId do not match an existing profile.
  4. Whether the unique indexes that prevent duplicates exist.

Usage (from the backend directory, against a STAGING copy or with read-only credentials):
    python -m scripts.audit_doctor_data            # summary
    python -m scripts.audit_doctor_data --details  # include document IDs (no names, emails or phones)

Remediation is intentionally manual: merging or deleting doctor records affects appointments,
payments and reviews and must be reviewed by an administrator. See
docs/COMPREHENSIVE_SYSTEM_AUDIT.md ("Data remediation plan").
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import re
import sys

from bson import ObjectId
from bson.decimal128 import Decimal128

from app.config.database import DatabaseManager


def _norm(value) -> str:
    return re.sub(r"\s+", " ", re.sub(r"^dr\.?\s+", "", str(value or ""), flags=re.I)).strip().casefold()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--details", action="store_true", help="print affected document IDs")
    args = parser.parse_args()

    db = DatabaseManager.get_database()
    profiles = list(db["doctor_profiles"].find({}, {"userId": 1, "doctorId": 1, "medicalRegistrationNumber": 1,
                                                    "specialty": 1, "consultationFee": 1, "verificationStatus": 1}))
    user_ids = [ObjectId(p["userId"]) for p in profiles if ObjectId.is_valid(str(p.get("userId")))]
    names = {str(u["_id"]): u.get("fullName") for u in db["users"].find({"_id": {"$in": user_ids}}, {"fullName": 1})}

    print(f"doctor_profiles: {len(profiles)}")

    # 1. Duplicates
    for field in ("userId", "doctorId", "medicalRegistrationNumber"):
        groups = defaultdict(list)
        for p in profiles:
            if p.get(field):
                groups[str(p[field])].append(str(p["_id"]))
        dupes = {k: v for k, v in groups.items() if len(v) > 1}
        print(f"duplicate {field}: {len(dupes)} value(s)")
        if args.details:
            for ids in dupes.values():
                print(f"   profiles: {', '.join(ids)}")
    by_identity = defaultdict(list)
    for p in profiles:
        name = _norm(names.get(str(p.get("userId"))))
        if name:
            by_identity[(name, _norm(p.get("specialty")))].append(str(p["_id"]))
    possible = [ids for ids in by_identity.values() if len(ids) > 1]
    print(f"possible duplicate people (same name + specialty, different accounts): {len(possible)}")
    if args.details:
        for ids in possible:
            print(f"   profiles: {', '.join(ids)}")

    # 2. Fees
    kinds = Counter()
    for p in profiles:
        fee = p.get("consultationFee", "<missing>")
        if fee == "<missing>":
            kinds["missing"] += 1
        elif fee is None:
            kinds["null"] += 1
        elif isinstance(fee, bool):
            kinds["boolean"] += 1
        elif isinstance(fee, Decimal128):
            kinds["decimal128"] += 1
        elif isinstance(fee, (int, float)):
            kinds["negative" if fee < 0 else "number"] += 1
        elif isinstance(fee, str):
            kinds["string"] += 1
        else:
            kinds[type(fee).__name__] += 1
    print("consultationFee storage:", dict(kinds))
    approved_without_fee = sum(1 for p in profiles if p.get("verificationStatus") == "APPROVED"
                               and not isinstance(p.get("consultationFee"), (int, float, str, Decimal128)))
    print(f"approved doctors without a usable fee (cannot be booked after BUG-028 fix): {approved_without_fee}")

    # 3. Orphaned availability
    profile_ids = {str(p["_id"]) for p in profiles}
    orphans = db["doctor_availabilities"].count_documents({"doctorProfileId": {"$nin": list(profile_ids)}})
    print(f"doctor_availabilities with unknown doctorProfileId: {orphans}")

    # 4. Indexes
    index_names = {ix["name"] for ix in db["doctor_profiles"].list_indexes()}
    for name in ("idx_doctor_profiles_user_id_unique", "idx_doctor_profiles_doctor_id_unique",
                 "idx_doctor_profiles_med_reg_no_unique"):
        print(f"index {name}: {'present' if name in index_names else 'MISSING'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
