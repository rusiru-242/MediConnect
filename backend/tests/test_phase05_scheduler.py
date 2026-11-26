"""Phase 05 S-06: durable reminder scheduler under real concurrency, restarts, crashes, cancellation, schedule
changes and Asia/Colombo day boundaries.

Runs in its own local database (mediconnect_p05sched_test, dropped afterwards) with a fixed far-future clock, so the
scheduler's expiry sweeps cannot touch other tests' reminders. Every channel except the in-app store is unconfigured
or disabled by preference, so nothing is sent externally.
"""
from datetime import datetime, timedelta, timezone
import os
import subprocess
import sys
import textwrap

from bson import ObjectId
import pytest

from app.services import care_scheduler as scheduler
from app.services.care_scheduler import COLOMBO

DB_NAME = "mediconnect_p05sched_test"
# 2041-03-10 00:30 Asia/Colombo = 2041-03-09 19:00 UTC; its 2-hour reminder is due 17:00 UTC (22:30 the day before
# in Colombo): the reminder falls on a different Colombo date than the appointment.
APPT_LOCAL = datetime(2041, 3, 10, 0, 30, tzinfo=COLOMBO)
DUE = APPT_LOCAL.astimezone(timezone.utc) - timedelta(hours=2)
NOW = DUE + timedelta(minutes=1)


@pytest.fixture
def sdb():
    from app.config.database import DatabaseManager
    client = DatabaseManager.get_client()
    client.drop_database(DB_NAME)
    db = client[DB_NAME]
    scheduler.create_indexes(db)
    yield db
    client.drop_database(DB_NAME)


def _patient(db):
    oid = ObjectId()
    db["users"].insert_one({"_id": oid, "role": "PATIENT", "fullName": "Sched Patient", "emailVerified": True,
                            "accountStatus": "ACTIVE", "email": f"sched_{oid}@mediconnect.lk",
                            "notificationPreferences": {"pushNotifications": False}})
    return str(oid)


def _appointment(db, patient_id, local=APPT_LOCAL):
    oid = ObjectId()
    db["appointments"].insert_one({"_id": oid, "patientUserId": patient_id, "doctorUserId": str(ObjectId()),
                                   "status": "CONFIRMED", "appointmentDate": local.date().isoformat(),
                                   "startTime": local.strftime("%H:%M")})
    return oid


def _events(db, appt_id):
    return list(db["care_reminder_events"].find({"sourceId": str(appt_id)}))


def test_s06h_colombo_day_boundary_and_machine_timezone_independence(sdb):
    pid = _patient(sdb)
    appt = _appointment(sdb, pid)
    assert scheduler.run_scheduler(sdb, NOW - timedelta(minutes=2)) == 0     # not due yet
    assert scheduler.run_scheduler(sdb, NOW) == 1
    (event,) = _events(sdb, appt)
    assert scheduler.utc(event["dueAt"]) == DUE and event["kind"] == "appointment"
    assert scheduler.utc(event["dueAt"]).astimezone(COLOMBO).date() != APPT_LOCAL.date()
    assert event["channels"]["inApp"]["status"] == "stored" and event["channels"]["push"]["status"] == "skipped"


def test_s06ab_execution_once_and_restart_does_not_redeliver(sdb):
    pid = _patient(sdb)
    appt = _appointment(sdb, pid)
    assert scheduler.run_scheduler(sdb, NOW) == 1
    for later in (NOW + timedelta(seconds=30), NOW + timedelta(minutes=20)):   # a restarted worker runs again
        assert scheduler.run_scheduler(sdb, later) == 0
    assert len(_events(sdb, appt)) == 1
    assert sdb["notifications"].count_documents({"recipientUserId": pid}) == 1


def test_s06c_crash_after_claim_is_not_resent_and_is_visible(sdb):
    pid = _patient(sdb)
    appt = _appointment(sdb, pid)
    row = next(scheduler.occurrences(sdb, "appointments", sdb["appointments"].find_one({"_id": appt}),
                                     DUE, DUE + timedelta(seconds=1)))
    scheduler.materialize(sdb, row)
    # A worker claimed it and crashed (possibly after the provider accepted the message): the lease runs out.
    sdb["care_reminder_events"].update_one({"_id": row["_id"]}, {"$set": {
        "state": "sending", "leaseUntil": NOW - timedelta(minutes=1), "attempts": 1}})
    assert scheduler.run_scheduler(sdb, NOW) == 0
    (event,) = _events(sdb, appt)
    assert event["state"] == "uncertain"  # never blindly re-sent; shown in notification monitoring
    assert sdb["notifications"].count_documents({"recipientUserId": pid}) == 0
    from app.services.notification_monitoring_service import NotificationMonitoringService
    states = NotificationMonitoringService.get_notification_metrics(sdb)["careReminderEvents"]
    assert states.get("uncertain") == 1


def test_s06f_cancellation_before_delivery_cancels_the_reminder(sdb):
    pid = _patient(sdb)
    appt = _appointment(sdb, pid)
    row = next(scheduler.occurrences(sdb, "appointments", sdb["appointments"].find_one({"_id": appt}),
                                     DUE, DUE + timedelta(seconds=1)))
    scheduler.materialize(sdb, row)
    sdb["appointments"].update_one({"_id": appt}, {"$set": {"status": "CANCELLED"}})
    scheduler.run_scheduler(sdb, NOW)
    assert _events(sdb, appt)[0]["state"] == "cancelled"
    assert sdb["notifications"].count_documents({"recipientUserId": pid}) == 0


def test_s06g_schedule_update_replaces_the_old_reminder(sdb):
    pid = _patient(sdb)
    appt = _appointment(sdb, pid)
    row = next(scheduler.occurrences(sdb, "appointments", sdb["appointments"].find_one({"_id": appt}),
                                     DUE, DUE + timedelta(seconds=1)))
    scheduler.materialize(sdb, row)
    new_local = APPT_LOCAL + timedelta(minutes=30)
    sdb["appointments"].update_one({"_id": appt}, {"$set": {"startTime": new_local.strftime("%H:%M")}})
    scheduler.run_scheduler(sdb, NOW)
    assert _events(sdb, appt)[0]["state"] == "cancelled"  # the old time is obsolete
    later = new_local.astimezone(timezone.utc) - timedelta(hours=2) + timedelta(minutes=1)
    assert scheduler.run_scheduler(sdb, later) == 1
    states = sorted(e["state"] for e in _events(sdb, appt))
    assert states == ["cancelled", "processed"]
    assert sdb["notifications"].count_documents({"recipientUserId": pid}) == 1


def test_s06de_three_worker_processes_deliver_each_reminder_exactly_once(sdb):
    pids = [_patient(sdb) for _ in range(4)]
    appts = [_appointment(sdb, pid, APPT_LOCAL + timedelta(minutes=i % 3)) for i, pid in enumerate(pids * 3)]
    code = textwrap.dedent(f"""
        from datetime import datetime
        from app.config.database import DatabaseManager
        from app.services import care_scheduler as s
        db = DatabaseManager.get_client()["{DB_NAME}"]
        now = datetime.fromisoformat("{(NOW + timedelta(minutes=3)).isoformat()}")
        print("SENT", s.run_scheduler(db, now))
    """)
    root = os.path.dirname(os.path.dirname(__file__))
    env = dict(os.environ)
    procs = [subprocess.Popen([sys.executable, "-c", code], cwd=root, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True) for _ in range(3)]
    sent = 0
    for p in procs:
        out, err = p.communicate(timeout=180)
        assert "SENT" in out, err[-600:]
        sent += int(out.split("SENT")[1].split()[0])
    events = [e for a in appts for e in _events(sdb, a)]
    assert len(events) == len(appts)                                   # no duplicate reminder rows
    assert sent == len(appts)                                         # each delivered by exactly one worker
    for e in events:
        attempts = [a for a in e.get("deliveryAttempts", []) if a["channel"] == "inApp"]
        assert len(attempts) == 1 and e["state"] == "processed", (e["state"], e.get("deliveryAttempts"),
                                                                   e.get("channels"), e.get("attempts"))
    per_event = list(sdb["notifications"].aggregate([{"$group": {"_id": "$relatedCareEventId", "n": {"$sum": 1}}}]))
    assert len(per_event) == len(appts) and all(row["n"] == 1 for row in per_event)
