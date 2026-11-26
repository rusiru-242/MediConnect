"""Phase 05 P4-B6: READ-ONLY report of paid cancellations that have no refund request (isolated UAT only).

Run:  python -I docs/uat/phase-05/p4b6_reconciliation_report.py OUT.json
Connects only to mongodb://127.0.0.1:27017 / mediconnect_uat and refuses anything else. It issues find/count
queries only: no record is created, changed or deleted, and no refund is backfilled. The same query can be run by
the owner against another database only with explicit authorization (see PHASE_05_OWNER_ACTION_CHECKLIST.md).
Output masks payment intent ids; no patient names, e-mails or phone numbers are included.
"""
import json
import pathlib
import sys

from pymongo import MongoClient

URI, NAME = "mongodb://127.0.0.1:27017", "mediconnect_uat"


def mask(value):
    return (value[:6] + "…" + value[-4:]) if isinstance(value, str) and len(value) > 12 else value


def main(out):
    assert URI.startswith("mongodb://127.0.0.1") and NAME.endswith("_uat")
    db = MongoClient(URI, serverSelectionTimeoutMS=3000, tz_aware=True)[NAME]
    cancelled = db["appointments"].find({"status": "CANCELLED", "paymentStatus": {"$in": ["PAID", "REFUND_PENDING"]}},
                                        {"cancelledBy": 1, "cancellationReason": 1, "appointmentDate": 1,
                                         "stripePaymentIntentId": 1, "consultationFee": 1, "bookingCurrency": 1,
                                         "updatedAt": 1})
    rows, by_actor = [], {}
    for appt in cancelled:
        aid = str(appt["_id"])
        if db["refund_requests"].count_documents({"appointmentId": aid}):
            continue
        payment = db["payments"].find_one({"appointmentId": aid}, {"status": 1, "amount": 1, "currency": 1,
                                                                    "refundedAmount": 1, "reconciliationState": 1})
        actor = appt.get("cancelledBy") or "unknown"
        by_actor[actor] = by_actor.get(actor, 0) + 1
        rows.append({"appointmentId": aid, "appointmentDate": appt.get("appointmentDate"), "cancelledBy": actor,
                     "paymentIntent": mask(appt.get("stripePaymentIntentId")),
                     "paymentStatus": (payment or {}).get("status"), "captured": (payment or {}).get("amount"),
                     "currency": ((payment or {}).get("currency") or appt.get("bookingCurrency") or "").upper() or None,
                     "alreadyRefunded": (payment or {}).get("refundedAmount") or 0,
                     "reconciliationState": (payment or {}).get("reconciliationState"),
                     "suggestedAction": "Admin review through payment reconciliation; no automatic backfill"})
    result = {"database": f"{NAME} (local, synthetic)", "readOnly": True,
              "paidCancellationsWithoutRefundRequest": len(rows), "byCancelledBy": by_actor, "rows": rows,
              "note": "P4-B6 remains an owner decision for any other database; nothing was changed here."}
    pathlib.Path(out).write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}))


if __name__ == "__main__":
    main(sys.argv[1])
