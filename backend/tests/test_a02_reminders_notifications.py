"""A02: reminder automation, notification delivery and patient communication (agents 05, 07, 08, 09, 13, 19).

Everything runs against local MongoDB (own database ``mediconnect_a02_unit_test``, dropped afterwards) and, for
e-mail, a real SMTP server bound to 127.0.0.1 inside this test process. No external provider is contacted: conftest
blanks every provider setting and blocks real SMTP/Twilio/FCM hosts at the socket level (A02-BUG-002).

"Mocked" below means a controlled test double; nothing here is evidence of external delivery.
"""
from datetime import datetime, timedelta, timezone
import datetime as _dt
import ipaddress
import os
import socket
import ssl
import subprocess
import sys
import textwrap
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch

from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from app.services import booking_notifications, care_scheduler as scheduler, email_service
from app.services.care_scheduler import COLOMBO
from app.services.email_service import EmailService
from app.services.notification_service import NotificationService, push_preview, _permanent_token_error
from tests.test_ai_booking_agent import seeded_booking_env  # noqa: F401  (fixture)

DB_NAME = "mediconnect_a02_unit_test"
APPT_LOCAL = datetime(2042, 6, 3, 9, 0, tzinfo=COLOMBO)
DUE = APPT_LOCAL.astimezone(timezone.utc) - timedelta(hours=24)
NOW = DUE + timedelta(minutes=1)


@pytest.fixture
def adb():
    from app.config.database import DatabaseManager
    client = DatabaseManager.get_client()
    client.drop_database(DB_NAME)
    db = client[DB_NAME]
    scheduler.create_indexes(db)
    from app.models.notification import create_notification_indexes
    create_notification_indexes(db)
    yield db
    client.drop_database(DB_NAME)


def _patient(db, **prefs):
    oid = ObjectId()
    db["users"].insert_one({"_id": oid, "role": "PATIENT", "fullName": "A02 Synthetic Patient", "emailVerified": True,
                            "accountStatus": "ACTIVE", "email": f"a02_{oid}@uat.mediconnect.lk",
                            "notificationPreferences": {"pushNotifications": False, **prefs}})
    return str(oid)


def _appointment(db, patient_id, local=APPT_LOCAL, status="CONFIRMED", **extra):
    oid = ObjectId()
    db["appointments"].insert_one({"_id": oid, "patientUserId": patient_id, "doctorUserId": str(ObjectId()),
                                   "status": status, "appointmentDate": local.date().isoformat(),
                                   "startTime": local.strftime("%H:%M"), "appointmentVersion": 1, **extra})
    return oid


def _events(db, source_id):
    return list(db["care_reminder_events"].find({"sourceId": str(source_id)}))


# ============================================================================ local SMTP server (127.0.0.1 only)
class LocalSMTP(threading.Thread):
    """Minimal ESMTP server for integration tests. Modes: ok, drop_after_data, data_451. Recipients containing
    "invalid" are refused with 550. With ``tls`` set it offers STARTTLS with that server context."""

    def __init__(self, mode="ok", tls=None, offer_starttls=True):
        super().__init__(daemon=True)
        self.mode, self.tls, self.offer_starttls = mode, tls, offer_starttls
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        # Blocking listener: on Windows an accepted socket inherits a listener timeout, which made reads time out.
        self.port = self.sock.getsockname()[1]
        self.messages, self.connections, self.stop_flag = [], 0, False

    def run(self):
        while not self.stop_flag:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            if self.stop_flag:
                conn.close()
                return
            conn.setblocking(True)
            self.connections += 1
            try:
                self._session(conn)
            except (OSError, ssl.SSLError):
                pass
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

    def _session(self, conn):
        conn.settimeout(30)  # smtplib resolves socket.getfqdn() for EHLO, which can take seconds on Windows
        reader = conn.makefile("rb")
        send = lambda line: conn.sendall(line.encode() + b"\r\n")  # noqa: E731
        send("220 a02-local ESMTP")
        upgraded, rcpts = False, []
        while True:
            raw = reader.readline()
            if not raw:
                return
            line = raw.decode(errors="replace").strip()
            verb = line[:4].upper()
            if verb in ("EHLO", "HELO"):
                if self.tls and self.offer_starttls and not upgraded:
                    send("250-a02-local")
                    send("250 STARTTLS")
                else:
                    send("250 a02-local")
            elif line.upper() == "STARTTLS":
                send("220 ready for TLS")
                conn = self.tls.wrap_socket(conn, server_side=True)
                reader = conn.makefile("rb")
                send = lambda l, c=conn: c.sendall(l.encode() + b"\r\n")  # noqa: E731,E741
                upgraded = True
            elif verb == "MAIL":
                rcpts = []
                send("250 OK")
            elif verb == "RCPT":
                address = line.split(":", 1)[1].strip(" <>")
                if "invalid" in address:
                    send("550 5.1.1 mailbox unavailable")
                else:
                    rcpts.append(address)
                    send("250 OK")
            elif verb == "DATA":
                send("354 end with .")
                body = b""
                while not body.endswith(b"\r\n.\r\n"):
                    chunk = reader.readline()
                    if not chunk:
                        return
                    body += chunk
                if self.mode == "drop_after_data":
                    conn.close()
                    return
                if self.mode == "data_451":
                    send("451 4.3.0 try again later")
                    continue
                self.messages.append({"rcpts": rcpts, "data": body.decode(errors="replace")})
                send("250 queued as A02")
            elif verb == "QUIT":
                send("221 bye")
                return
            else:
                send("250 OK")

    def close(self):
        self.stop_flag = True
        try:
            socket.create_connection(("127.0.0.1", self.port), timeout=1).close()   # wake accept()
        except OSError:
            pass
        self.join(timeout=3)
        self.sock.close()


def _self_signed(tmp_path):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "a02-local-test")])
    now = _dt.datetime.now(_dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), True)
            .sign(key, hashes.SHA256()))
    cert_path, key_path = tmp_path / "a02_cert.pem", tmp_path / "a02_key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                           serialization.NoEncryption()))
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.load_cert_chain(cert_path, key_path)
    return server, cert_path


@pytest.fixture
def smtp(monkeypatch):
    servers = []

    def start(mode="ok", tls=None, offer_starttls=True, plaintext=True):
        server = LocalSMTP(mode, tls, offer_starttls)
        server.start()
        servers.append(server)
        monkeypatch.setattr(email_service.settings, "SMTP_HOST", "127.0.0.1")
        monkeypatch.setattr(email_service.settings, "SMTP_PORT", server.port)
        monkeypatch.setattr(email_service.settings, "SMTP_USERNAME", None)
        monkeypatch.setattr(email_service.settings, "SMTP_PASSWORD", None)
        monkeypatch.setattr(email_service.settings, "SMTP_FROM_EMAIL", "noreply@uat.mediconnect.lk")
        monkeypatch.setenv("SMTP_ALLOW_PLAINTEXT_LOOPBACK", "true" if plaintext else "false")
        return server

    yield start
    for server in servers:
        server.close()


# ============================================================================ e-mail (A02-I04, A02-I08, A02-I09)
def test_i04_local_smtp_accepts_and_records_message(smtp):
    server = smtp()
    outcome = EmailService._send_email("a02.patient@uat.mediconnect.lk", "MediConnect test", "plain body", "<p>x</p>")
    assert outcome.status == "accepted" and bool(outcome) is True
    (message,) = server.messages
    assert message["rcpts"] == ["a02.patient@uat.mediconnect.lk"] and "MediConnect test" in message["data"]


def test_bug001_smtp_tls_certificate_is_verified(smtp, tmp_path, monkeypatch):
    context, cert_path = _self_signed(tmp_path)
    server = smtp(tls=context, plaintext=False)
    # Untrusted (self-signed) certificate: before A02 smtplib used an unverified context and this was accepted.
    monkeypatch.delenv("SMTP_CA_FILE", raising=False)
    refused = EmailService._send_email("a02.patient@uat.mediconnect.lk", "s", "t", "h")
    assert refused.status == "retry" and refused.reason == "tls_failed" and server.messages == []
    # Trusted CA: the same server is accepted over verified TLS.
    monkeypatch.setenv("SMTP_CA_FILE", str(cert_path))
    assert EmailService._send_email("a02.patient@uat.mediconnect.lk", "s", "t", "h").status == "accepted"
    assert len(server.messages) == 1
    ctx = email_service._tls_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname is True


def test_bug001_plaintext_is_refused_outside_explicit_loopback_test_mode(smtp):
    server = smtp(plaintext=False)  # no STARTTLS offered, plaintext not allowed
    outcome = EmailService._send_email("a02.patient@uat.mediconnect.lk", "s", "t", "h")
    assert outcome.status == "rejected" and outcome.reason == "starttls_unavailable" and server.messages == []


@pytest.mark.parametrize("mode, recipient, status, reason", [
    ("ok", "invalid.mailbox@uat.mediconnect.lk", "rejected", "recipient_refused"),   # invalid recipient
    ("drop_after_data", "a02@uat.mediconnect.lk", "uncertain", "connection_lost_during_submission"),
    ("data_451", "a02@uat.mediconnect.lk", "retry", "data_refused"),
])
def test_bug003_smtp_outcomes_are_classified(smtp, mode, recipient, status, reason):
    smtp(mode=mode)
    outcome = EmailService._send_email(recipient, "s", "t", "h")
    assert (outcome.status, outcome.reason) == (status, reason)
    assert bool(outcome) is False


def test_bug003_connection_refused_is_retry_and_unconfigured_is_disabled(monkeypatch):
    closed = socket.socket()
    closed.bind(("127.0.0.1", 0))
    port = closed.getsockname()[1]
    closed.close()  # nothing listens on this port
    monkeypatch.setattr(email_service.settings, "SMTP_HOST", "127.0.0.1")
    monkeypatch.setattr(email_service.settings, "SMTP_PORT", port)
    assert EmailService._send_email("a@uat.mediconnect.lk", "s", "t", "h").status == "retry"
    monkeypatch.setattr(email_service.settings, "SMTP_HOST", None)
    outcome = EmailService._send_email("a@uat.mediconnect.lk", "s", "t", "h")
    assert (outcome.status, outcome.reason) == ("disabled", "provider_not_configured")


def test_bug002_real_smtp_hosts_are_blocked_in_tests(monkeypatch):
    monkeypatch.setattr(email_service.settings, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr(email_service.settings, "SMTP_PORT", 587)
    assert os.environ.get("SMTP_PASSWORD", "") == ""       # never inherited from backend/.env
    assert EmailService._send_email("a@uat.mediconnect.lk", "s", "t", "h").status == "retry"


def _confirmed(db, patient_id, **extra):
    return db["appointments"].find_one({"_id": _appointment(
        db, patient_id, confirmedAt=datetime.now(timezone.utc), paymentStatus="PAID", bookingDoctorName="Dr. A02 Synthetic",
        confirmationOutbox={"email": {"status": "pending", "attempts": 0, "nextAttemptAt": datetime.now(timezone.utc)}},
        **extra)})


def test_i04_booking_confirmation_email_through_local_smtp_once(adb, smtp, monkeypatch):
    server = smtp()
    pid = _patient(adb)
    appt = _confirmed(adb, pid)
    monkeypatch.setattr(booking_notifications, "twilio_config", lambda: ("", "", ""))
    booking_notifications.run_confirmation_outbox(adb)
    booking_notifications.run_confirmation_outbox(adb)      # duplicate prevention
    entry = adb["appointments"].find_one({"_id": appt["_id"]})["confirmationOutbox"]["email"]
    assert entry["status"] == "sent" and entry["attempts"] == 1
    (message,) = server.messages
    assert message["rcpts"] == [adb["users"].find_one({"_id": ObjectId(pid)})["email"]]
    import email
    parsed = email.message_from_string(message["data"].rsplit("\r\n.\r\n", 1)[0])
    text = next(part.get_payload(decode=True).decode() for part in parsed.walk()
                if part.get_content_type() == "text/plain")
    assert "Dr. A02 Synthetic" in text and str(appt["_id"]) in text


def test_i04_doctor_verification_emails_render_through_local_smtp(smtp):
    import email
    server = smtp()
    assert EmailService.send_doctor_approval_email(
        "a02.doctor@uat.mediconnect.lk", "Dr. A02 Synthetic", "Cardiology", "SLMC-A02-0001", "UAT Synthetic Hospital")
    assert EmailService.send_doctor_rejection_email("a02.doctor2@uat.mediconnect.lk", "Dr. A02 Rejected",
                                                    reason="Synthetic: registration number could not be verified")
    approval, rejection = server.messages
    texts = []
    for message in (approval, rejection):
        parsed = email.message_from_string(message["data"].rsplit("\r\n.\r\n", 1)[0])
        texts.append(next(p.get_payload(decode=True).decode() for p in parsed.walk() if p.get_content_type() == "text/plain"))
    assert approval["rcpts"] == ["a02.doctor@uat.mediconnect.lk"] and "SLMC-A02-0001" in texts[0]
    assert rejection["rcpts"] == ["a02.doctor2@uat.mediconnect.lk"] and "could not be verified" in texts[1]


def test_i08_i09_outbox_disabled_and_transient_failure(adb, monkeypatch):
    pid = _patient(adb)
    appt = _confirmed(adb, pid)
    monkeypatch.setattr(booking_notifications.settings, "SMTP_HOST", None)
    booking_notifications.run_confirmation_outbox(adb)
    entry = adb["appointments"].find_one({"_id": appt["_id"]})["confirmationOutbox"]["email"]
    assert (entry["status"], entry["reason"]) == ("disabled", "provider_not_configured")   # not "failed"/"sent"
    # A transient failure before transmission is retried, bounded by the attempt limit.
    other = _confirmed(adb, _patient(adb))
    monkeypatch.setattr(booking_notifications.settings, "SMTP_HOST", "127.0.0.1")
    monkeypatch.setattr(booking_notifications.EmailService, "_send_email",
                        Mock(return_value=email_service.EmailOutcome("retry", "connection_failed")))
    booking_notifications.run_confirmation_outbox(adb)
    entry = adb["appointments"].find_one({"_id": other["_id"]})["confirmationOutbox"]["email"]
    assert entry["status"] == "pending" and entry["reason"] == "connection_failed" and entry["nextAttemptAt"]


def test_i06_i07_sms_disabled_without_provider_and_never_reported_delivered(adb):
    pid = _patient(adb)
    adb["users"].update_one({"_id": ObjectId(pid)}, {"$set": {"phone": "0771234567"}})
    appt = adb["appointments"].find_one({"_id": _appointment(
        adb, pid, smsConsent=True, smsDestinationHash=booking_notifications.phone_fingerprint("0771234567"),
        paymentStatus="PAID")})
    assert booking_notifications.normalize_phone("077 123 4567") == "+94771234567"
    assert booking_notifications.normalize_phone("0112345678") is None       # landline cannot receive SMS
    result = booking_notifications.send_confirmation(adb, appt, "sms")
    assert result == {"status": "disabled", "reason": "provider_not_configured"}


# ============================================================================ scheduler and delivery state
def test_bug004_unconfigured_channels_are_disabled_not_failed(adb, monkeypatch):
    pid = _patient(adb, careEmail=True, pushNotifications=True)
    _appointment(adb, pid)
    assert scheduler.run_scheduler(adb, NOW) == 1
    (event,) = [e for e in adb["care_reminder_events"].find({"patientUserId": pid})]
    channels = {k: v["status"] for k, v in event["channels"].items()}
    assert channels == {"inApp": "stored", "push": "disabled", "email": "disabled", "sms": "skipped"}
    from app.services.notification_monitoring_service import NotificationMonitoringService
    rows = {c["channel"]: c for c in NotificationMonitoringService.get_notification_metrics(adb)["byChannel"]}
    assert rows["push"]["disabled"] == 1 and rows["push"]["delivered"] == 0 and rows["push"]["accepted"] == 0
    assert rows["email"]["disabled"] == 1 and rows["email"]["failed"] == 0
    assert rows["in_app"]["delivered"] == 1


def test_bug004_provider_acceptance_is_not_counted_as_delivery(adb):
    adb["appointments"].insert_one({"status": "CONFIRMED", "confirmationOutbox": {
        "email": {"status": "sent"}, "sms": {"status": "accepted"}}})
    adb["appointments"].insert_one({"status": "CONFIRMED", "confirmationOutbox": {"sms": {"status": "delivered"}}})
    from app.services.notification_monitoring_service import NotificationMonitoringService
    rows = {c["channel"]: c for c in NotificationMonitoringService.get_notification_metrics(adb)["byChannel"]}
    assert (rows["email"]["accepted"], rows["email"]["delivered"]) == (1, 0)
    assert (rows["sms"]["accepted"], rows["sms"]["delivered"]) == (1, 1)    # only a provider receipt is "delivered"


def test_s04_real_worker_crash_mid_delivery_recovers_in_app_exactly_once(adb):
    """A real worker process dies (os._exit) while writing the in-app reminder; another worker recovers it."""
    pid = _patient(adb)
    appt = _appointment(adb, pid)
    code = textwrap.dedent(f"""
        import os
        from datetime import datetime
        from app.config.database import DatabaseManager
        from app.services import care_scheduler as s
        db = DatabaseManager.get_client()["{DB_NAME}"]
        def crash(*a, **k):
            os._exit(3)   # the process dies with the in-app channel marked "sending"
        s.NotificationService.create_notification = crash
        s.run_scheduler(db, datetime.fromisoformat("{NOW.isoformat()}"))
    """)
    root = os.path.dirname(os.path.dirname(__file__))
    proc = subprocess.run([sys.executable, "-c", code], cwd=root, env=dict(os.environ), capture_output=True,
                          text=True, timeout=180)
    assert proc.returncode == 3, proc.stderr[-600:]
    (event,) = _events(adb, appt)
    assert event["state"] == "sending" and event["channels"]["inApp"]["status"] == "sending"
    assert adb["notifications"].count_documents({"recipientUserId": pid}) == 0
    # Lease not yet expired: a second worker does not touch it.
    assert scheduler.run_scheduler(adb, NOW + timedelta(minutes=1)) == 0
    # Lease expired: recovered, delivered once; further runs do nothing.
    assert scheduler.run_scheduler(adb, NOW + timedelta(minutes=4)) == 1
    assert scheduler.run_scheduler(adb, NOW + timedelta(minutes=30)) == 0
    (event,) = _events(adb, appt)
    assert event["state"] == "processed" and event["recoveries"] == 1
    assert adb["notifications"].count_documents({"recipientUserId": pid}) == 1


def test_s08_permanent_failure_after_bounded_retries(adb, monkeypatch):
    pid = _patient(adb)
    appt = _appointment(adb, pid)
    monkeypatch.setattr(scheduler.NotificationService, "create_notification", Mock(return_value=None))
    clock = NOW
    for _ in range(6):
        scheduler.run_scheduler(adb, clock)
        clock += timedelta(minutes=40)
        if clock >= APPT_LOCAL.astimezone(timezone.utc) - timedelta(hours=20):
            break
    (event,) = _events(adb, appt)
    assert event["channels"]["inApp"]["status"] == "failed" and event["attempts"] == 4


def test_f02_follow_up_reminders_7d_1d_due_at_0900_colombo_once_each(adb):
    """The real scheduler with an injected clock: three reminders at 09:00 Asia/Colombo, each delivered once; a moved
    follow-up date cancels the remaining old ones."""
    pid = _patient(adb)
    follow = APPT_LOCAL.date() + timedelta(days=10)
    plan = adb["care_plans"].insert_one({"patientUserId": pid, "doctorUserId": str(ObjectId()), "status": "ACTIVE",
                                         "followUpDate": follow.isoformat(), "tasks": [],
                                         "instructions": "Synthetic"}).inserted_id
    nine = lambda day: datetime.combine(day, datetime.min.time().replace(hour=9), COLOMBO).astimezone(timezone.utc)  # noqa: E731
    for days in (7, 1):
        due = nine(follow - timedelta(days=days))
        assert scheduler.run_scheduler(adb, due - timedelta(minutes=1)) == 0      # not before 09:00
        assert scheduler.run_scheduler(adb, due + timedelta(minutes=1)) == 1
        assert scheduler.run_scheduler(adb, due + timedelta(minutes=30)) == 0     # once
    adb["care_plans"].update_one({"_id": plan}, {"$set": {"followUpDate": (follow + timedelta(days=3)).isoformat()}})
    assert scheduler.run_scheduler(adb, nine(follow) + timedelta(minutes=1)) == 0     # old due-day reminder obsolete
    events = list(adb["care_reminder_events"].find({"sourceId": str(plan)}))
    assert sorted(e["legacyMarker"] for e in events) == ["1D", "7D"]
    assert all(e["kind"] == "follow_up" and e["state"] == "processed" for e in events)
    assert adb["notifications"].count_documents({"recipientUserId": pid}) == 2


def test_s07_colombo_midnight_boundary_for_medication(adb):
    """23:30 Colombo is 18:00 UTC the same day; 00:15 Colombo is 18:45 UTC the previous UTC day."""
    pid = _patient(adb)
    for clock, expected_utc in (("23:30", datetime(2042, 6, 3, 18, 0, tzinfo=timezone.utc)),
                                ("00:15", datetime(2042, 6, 2, 18, 45, tzinfo=timezone.utc))):
        assert scheduler.local_at(APPT_LOCAL.date(), clock) == expected_utc


# ============================================================================ push (FCM) handling
def test_bug006_push_uses_generic_lock_screen_text_and_bug009_records_outcome(adb, monkeypatch):
    pid = _patient(adb, pushNotifications=True)
    push = Mock(return_value="accepted")
    monkeypatch.setattr(NotificationService, "_send_fcm_push", push)
    from app.models.notification import NotificationType
    notice = NotificationService.create_notification(
        adb, pid, NotificationType.APPOINTMENT_CONFIRMED, "Appointment Confirmed",
        "Your appointment with Dr. Synthetic Psychiatrist is confirmed for 2042-06-03 at 09:00.",
        related_appointment_id=str(ObjectId()), idempotency_key=f"a02_{pid}")
    kwargs = push.call_args.kwargs
    assert "Psychiatrist" not in kwargs["title"] + kwargs["body"] and "2042" not in kwargs["body"]
    assert (kwargs["title"], kwargs["body"]) == push_preview("APPOINTMENT_CONFIRMED")
    assert kwargs["data"]["relatedAppointmentId"] and kwargs["data"]["notificationId"] == notice.id
    stored = adb["notifications"].find_one({"_id": ObjectId(notice.id)})
    assert "Psychiatrist" in stored["body"]                      # the full text stays in the app
    assert stored["channels"]["push"]["status"] == "accepted"
    # Push turned off by the patient: in-app only, recorded as skipped. Firebase unconfigured: disabled.
    adb["users"].update_one({"_id": ObjectId(pid)}, {"$set": {"notificationPreferences.pushNotifications": False}})
    off = NotificationService.create_notification(adb, pid, NotificationType.SYSTEM, "t", "b")
    assert adb["notifications"].find_one({"_id": ObjectId(off.id)})["channels"]["push"]["status"] == "skipped"
    monkeypatch.setattr(NotificationService, "_send_fcm_push", Mock(return_value="unavailable"))
    adb["users"].update_one({"_id": ObjectId(pid)}, {"$set": {"notificationPreferences.pushNotifications": True}})
    dis = NotificationService.create_notification(adb, pid, NotificationType.SYSTEM, "t", "b")
    assert adb["notifications"].find_one({"_id": ObjectId(dis.id)})["channels"]["push"]["status"] == "disabled"


def test_bug007_only_permanent_token_errors_remove_tokens():
    from firebase_admin import messaging
    assert _permanent_token_error(messaging.UnregisteredError("Requested entity was not found."))
    assert _permanent_token_error(messaging.SenderIdMismatchError("mismatch"))
    quota = messaging.QuotaExceededError("quota")
    assert not _permanent_token_error(quota)
    payload_error = SimpleNamespace(code="invalid-argument")
    assert not _permanent_token_error(payload_error)              # a bad payload must not delete devices
    bad_token = Exception("The registration token is not a valid FCM registration token")
    bad_token.code = "invalid-argument"
    assert _permanent_token_error(bad_token)


def test_bug007_fcm_multicast_cleans_only_unregistered_tokens(adb, monkeypatch):
    from firebase_admin import messaging
    pid = _patient(adb)
    for t in ("tok-ok", "tok-gone", "tok-quota"):
        NotificationService.register_device_token(adb, pid, t)
    monkeypatch.setattr("app.services.notification_service._init_firebase", lambda: True)
    ok = SimpleNamespace(success=True, exception=None)
    gone = SimpleNamespace(success=False, exception=messaging.UnregisteredError("gone"))
    quota = SimpleNamespace(success=False, exception=messaging.QuotaExceededError("quota"))

    def fake_send(message):
        order = {"tok-ok": ok, "tok-gone": gone, "tok-quota": quota}
        return SimpleNamespace(success_count=1, failure_count=2, responses=[order[t] for t in message.tokens])

    monkeypatch.setattr(messaging, "send_each_for_multicast", fake_send)
    assert NotificationService._send_fcm_push(adb, pid, "t", "b", {"k": "v"}) == "accepted"
    remaining = sorted(d["fcmToken"] for d in adb["device_tokens"].find({"userId": pid}))
    assert remaining == ["tok-ok", "tok-quota"]


def test_bug008_device_list_bounded_type_validated_and_token_not_logged(adb, caplog):
    pid = _patient(adb)
    for i in range(12):
        NotificationService.register_device_token(adb, pid, f"device-token-{i:02d}")
    tokens = [d["fcmToken"] for d in adb["device_tokens"].find({"userId": pid})]
    assert len(tokens) == 10 and "device-token-00" not in tokens and "device-token-11" in tokens
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        NotificationService.register_device_token(adb, pid, "x", device_type="smartfridge")
    assert exc.value.status_code == 422
    with caplog.at_level("INFO"):
        NotificationService.clean_stale_token(adb, "device-token-11")
    assert "device-token" not in caplog.text


def test_bug010_monitoring_cleanup_removes_stored_tokens(adb):
    from app.services.notification_monitoring_service import NotificationMonitoringService
    pid = _patient(adb)
    NotificationService.register_device_token(adb, pid, "stale-token-a02")
    assert NotificationMonitoringService.cleanup_invalid_device_tokens(["stale-token-a02"], db=adb) == 1


# ============================================================================ medication reminder (agent 05)
def _rx(db, patient_id, item, status="ISSUED"):
    return db["prescriptions"].insert_one({
        "prescriptionId": f"RX-A02-{ObjectId()}", "patientUserId": patient_id, "doctorUserId": str(ObjectId()),
        "status": status, "medicationItems": [item]}).inserted_id


@pytest.mark.parametrize("frequency, duration", [
    ("PRN (As needed for mild headache)", "5 days"),   # as-needed medicine: no fixed reminders
    ("After food", "5 days"),                           # used to count as "od" (once daily)
    ("Once weekly", "4 weeks"),
    ("Twice daily", "until review"),                    # used to become an invented 7-day course
])
def test_bug011_patient_reminder_refused_without_fixed_prescribed_schedule(adb, frequency, duration):
    import asyncio
    from fastapi import HTTPException
    from app.schemas.medication_reminder import CreateMedicationReminderRequest
    from app.services.medication_reminder_service import MedicationReminderService
    pid = _patient(adb)
    rx = _rx(adb, pid, {"medicationName": "Synthopar", "dose": "1 tablet", "frequency": frequency,
                        "duration": duration, "route": "Oral"})
    user = SimpleNamespace(id=pid, role="PATIENT")
    req = CreateMedicationReminderRequest(prescriptionId=str(rx), prescriptionMedicationIndex=0,
                                          scheduledTimes=["08:00"], patientTimezone="Asia/Colombo")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(MedicationReminderService.create_reminder(adb, user, req))
    assert exc.value.status_code == 422 and "doctor" in exc.value.detail
    assert adb["medication_reminders"].count_documents({"patientUserId": pid}) == 0


def test_bug011_patient_reminder_cannot_outlast_prescribed_duration(adb):
    import asyncio
    from fastapi import HTTPException
    from app.schemas.medication_reminder import CreateMedicationReminderRequest
    from app.services.medication_reminder_service import MedicationReminderService
    pid = _patient(adb)
    rx = _rx(adb, pid, {"medicationName": "Synthomox", "strength": "250 mg", "dose": "1 capsule", "frequency": "Twice daily",
                        "duration": "5 days", "route": "Oral"})
    user = SimpleNamespace(id=pid, role="PATIENT")
    start = datetime.now(timezone.utc)
    base = dict(prescriptionId=str(rx), prescriptionMedicationIndex=0, scheduledTimes=["08:00", "20:00"],
                patientTimezone="Asia/Colombo", startDate=start)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(MedicationReminderService.create_reminder(
            adb, user, CreateMedicationReminderRequest(**base, endDate=start + timedelta(days=60))))
    assert exc.value.status_code == 422
    created = asyncio.run(MedicationReminderService.create_reminder(adb, user, CreateMedicationReminderRequest(**base)))
    assert created.scheduledTimes == ["08:00", "20:00"]
    assert abs((scheduler.utc(created.endDate) - start) - timedelta(days=5)) < timedelta(seconds=1)


# ============================================================================ care plan communication (agent 19)
def test_bug014_care_plan_update_and_close_notify_patient_once_without_clinical_text(adb):
    import asyncio
    from app.schemas.care_plan import CancelCarePlanRequest, UpdateCarePlanRequest
    from app.services.care_plan_service import CarePlanService
    pid, doctor_id = _patient(adb), str(ObjectId())
    plan = adb["care_plans"].insert_one({
        "patientUserId": pid, "doctorUserId": doctor_id, "appointmentId": str(ObjectId()), "status": "ACTIVE",
        "followUpDate": "2042-06-10", "instructions": "Synthetic instruction A", "version": 1, "tasks": [],
        "auditLog": [], "createdAt": datetime.now(timezone.utc)}).inserted_id
    doctor = SimpleNamespace(id=doctor_id, role="DOCTOR")
    asyncio.run(CarePlanService.update_care_plan(adb, doctor, str(plan), UpdateCarePlanRequest(
        followUpDate="2042-06-17", instructions="Synthetic instruction B (secret clinical detail)")))
    asyncio.run(CarePlanService.update_care_plan(adb, doctor, str(plan), UpdateCarePlanRequest(
        followUpDate="2042-06-17")))  # no change: no new notice
    notices = list(adb["notifications"].find({"recipientUserId": pid}))
    assert len(notices) == 1 and notices[0]["title"] == "Care plan updated"
    assert "secret clinical detail" not in notices[0]["body"] and "2042" not in notices[0]["body"]
    other = SimpleNamespace(id=str(ObjectId()), role="DOCTOR")
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:                     # an unrelated doctor cannot change it
        asyncio.run(CarePlanService.update_care_plan(adb, other, str(plan), UpdateCarePlanRequest(
            followUpDate="2042-07-01")))
    assert exc.value.status_code == 403
    asyncio.run(CarePlanService.cancel_care_plan(adb, doctor, str(plan), CancelCarePlanRequest(
        reason="Synthetic closure reason")))
    assert adb["notifications"].count_documents({"recipientUserId": pid}) == 2
    assert adb["notifications"].count_documents({"recipientUserId": pid, "title": "Care plan closed"}) == 1


# ============================================================================ AI intents (section 15)
@pytest.mark.parametrize("text, intent", [
    ("Show my medicine reminders for today.", "medication_schedule"),
    ("mata ada bonna thiyena beheth monawada?", "medication_schedule"),
    ("Show my missed medicine reminders.", "missed_medication"),
    ("Did I miss any doses yesterday?", "missed_medication"),
    ("Show my unread notifications.", "unread_notifications"),
    ("Do I have any new notifications?", "unread_notifications"),
    ("Mark all my notifications as read.", "notification_action"),
    ("What medical tests do I have this week?", "medical_tests"),
    ("change my dose to two tablets", "medication_change_request"),
    ("What is paracetamol used for?", "unknown"),
    ("I missed my bus, find a cardiologist", "unknown"),
])
def test_bug012_reminder_and_notification_questions_are_classified(text, intent):
    from app.agents.intent_router import classify
    assert classify("PATIENT", text).intent == intent


def test_bug012_assistant_answers_from_own_records_only(seeded_booking_env):
    """Through the real conversation endpoint: own unread notifications, no state change, other patient isolated."""
    from app.config.database import get_database
    from app.main import app
    from app.models.notification import NotificationType
    db, seed = get_database(), seeded_booking_env
    client = TestClient(app)
    for title in ("A02 synthetic notice one", "A02 synthetic notice two"):
        NotificationService.create_notification(db, seed["pat_a_id"], NotificationType.SYSTEM, title, "b",
                                                send_push=False)
    NotificationService.create_notification(db, seed["pat_b_id"], NotificationType.SYSTEM, "Patient B private",
                                            "b", send_push=False)
    unread_before = NotificationService.get_unread_count(db, seed["pat_a_id"])

    def ask(text, token):
        response = client.post("/api/ai/conversations", json={"initialMessage": text},
                               headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 201, response.text
        return [m for m in response.json()["messages"] if m["sender"] == "assistant"][-1]["content"]

    reply = ask("Show my unread notifications.", seed["token_patient_a"])
    assert f"You have {unread_before} unread" in reply and "A02 synthetic notice two" in reply
    assert "Patient B private" not in reply
    reply = ask("Mark all my notifications as read.", seed["token_patient_a"])
    assert "can't change your notifications" in reply
    assert NotificationService.get_unread_count(db, seed["pat_a_id"]) == unread_before   # nothing changed
    reply = ask("Show my missed medicine reminders.", seed["token_patient_a"])
    assert "without a recorded action" in reply.lower()
    assert "Could you please share your symptoms" not in reply


# ============================================================================ prescription availability (agent 19)
def test_bug021_issued_prescription_notifies_patient_once_without_medicine_names():
    from app.config.database import get_database
    from app.main import app
    from tests.test_phase02_booking_payment import _auth
    from tests.test_phase03_doctor_system import ITEM, _visit
    from tests.test_payment import _make_test_doctor, _make_test_patient
    db, client = get_database(), TestClient(app)
    patient, doctor = _make_test_patient(db, "A02B021"), _make_test_doctor(db, "A02B021Doc")
    visit = _visit(db, patient, doctor)
    res = client.post("/api/clinical/prescriptions/sign", headers=_auth(doctor),
                      json={"patientUserId": patient["id"], "appointmentId": visit, "medicationItems": [ITEM]})
    assert res.status_code == 201, res.text
    again = client.post("/api/clinical/prescriptions/sign", headers=_auth(doctor),
                        json={"patientUserId": patient["id"], "appointmentId": visit, "medicationItems": [ITEM]})
    assert again.status_code == 409
    notices = list(db["notifications"].find({"recipientUserId": patient["id"], "type": "PRESCRIPTION_ISSUED"}))
    assert len(notices) == 1 and notices[0]["relatedAppointmentId"] == visit
    assert ITEM["medicationName"] not in notices[0]["title"] + notices[0]["body"]
