"""Unit and integration tests for Phase 17 — MediConnect Notification System."""

from datetime import datetime, timedelta, timezone
import time
from typing import Any, Dict
from unittest.mock import MagicMock, patch
from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from app.config.database import DatabaseManager
from app.main import app
from app.models.appointment import AppointmentStatus, utc_now
from app.models.notification import (
    NotificationType,
    get_device_token_collection,
    get_notification_collection,
)
from app.models.user import AccountStatus, UserRole
from app.services.notification_service import NotificationService, SL_TIMEZONE
from app.utils.security import create_access_token, hash_password

client = TestClient(app)


@pytest.fixture(scope="module")
def db():
    return DatabaseManager.get_database()


def _uid() -> str:
    return f"{int(time.time() * 1000)}_{ObjectId()}"[:14]


def _make_test_user(db, suffix: str, role: str = UserRole.PATIENT.value) -> Dict[str, Any]:
    uid = _uid()
    oid = ObjectId()
    doc = {
        "_id": oid,
        "fullName": f"User {suffix}",
        "email": f"notif_{suffix}_{uid}@mediconnect.lk",
        "phone": "0771234567",
        "passwordHash": hash_password("Secret123!"),
        "role": role,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    }
    db["users"].insert_one(doc)
    token = create_access_token(user_id=str(oid), role=role)
    return {"doc": doc, "token": token, "id": str(oid)}


def test_unauthenticated_notification_endpoints():
    """Unauthenticated access to notification endpoints must return 401."""
    res = client.get("/api/notifications")
    assert res.status_code == 401

    res = client.get("/api/notifications/unread-count")
    assert res.status_code == 401

    res = client.patch(f"/api/notifications/{ObjectId()}/read")
    assert res.status_code == 401

    res = client.patch("/api/notifications/read-all")
    assert res.status_code == 401

    res = client.post("/api/notifications/devices", json={"fcmToken": "sample"})
    assert res.status_code == 401

    res = client.request("DELETE", "/api/notifications/devices", json={"fcmToken": "sample"})
    assert res.status_code == 401


def test_notification_creation_and_listing(db):
    """Create notification and verify retrieval with unread count."""
    user = _make_test_user(db, "listing")
    user_id = user["id"]
    headers = {"Authorization": f"Bearer {user['token']}"}

    # Verify initial empty state
    res = client.get("/api/notifications", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["unreadCount"] == 0
    assert data["items"] == []

    # Create notification directly via service
    notif = NotificationService.create_notification(
        db=db,
        recipient_user_id=user_id,
        type=NotificationType.BOOKING_CREATED,
        title="Test Booking",
        body="Your appointment slot has been reserved.",
        send_push=False,
    )
    assert notif is not None
    assert notif.recipientUserId == user_id
    assert notif.isRead is False

    # Check unread count endpoint
    count_res = client.get("/api/notifications/unread-count", headers=headers)
    assert count_res.status_code == 200
    assert count_res.json()["unreadCount"] == 1

    # Check list endpoint
    list_res = client.get("/api/notifications", headers=headers)
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] == 1
    assert list_data["unreadCount"] == 1
    assert list_data["items"][0]["id"] == notif.id
    assert list_data["items"][0]["title"] == "Test Booking"


def test_recipient_authorization_isolation(db):
    """User B cannot access or mark as read notifications belonging to User A."""
    user_a = _make_test_user(db, "isolation_a")
    user_b = _make_test_user(db, "isolation_b")

    # Create notification for User A
    notif_a = NotificationService.create_notification(
        db=db,
        recipient_user_id=user_a["id"],
        type=NotificationType.SYSTEM,
        title="Confidential A",
        body="Details for A",
        send_push=False,
    )

    # User B list notifications -> empty
    headers_b = {"Authorization": f"Bearer {user_b['token']}"}
    res = client.get("/api/notifications", headers=headers_b)
    assert res.status_code == 200
    assert res.json()["total"] == 0

    # User B tries to mark User A's notification as read -> 403 Forbidden
    patch_res = client.patch(f"/api/notifications/{notif_a.id}/read", headers=headers_b)
    assert patch_res.status_code == 403
    assert "permission" in patch_res.json()["detail"].lower()


def test_mark_as_read_and_mark_all_read(db):
    """Test mark single as read and mark all as read."""
    user = _make_test_user(db, "mark_read")
    user_id = user["id"]
    headers = {"Authorization": f"Bearer {user['token']}"}

    n1 = NotificationService.create_notification(
        db=db,
        recipient_user_id=user_id,
        type=NotificationType.APPOINTMENT_CONFIRMED,
        title="Confirmed 1",
        body="Body 1",
        send_push=False,
    )
    n2 = NotificationService.create_notification(
        db=db,
        recipient_user_id=user_id,
        type=NotificationType.APPOINTMENT_CONFIRMED,
        title="Confirmed 2",
        body="Body 2",
        send_push=False,
    )

    # Total 2 unread
    assert client.get("/api/notifications/unread-count", headers=headers).json()["unreadCount"] == 2

    # Mark n1 as read
    res1 = client.patch(f"/api/notifications/{n1.id}/read", headers=headers)
    assert res1.status_code == 200
    assert res1.json()["success"] is True

    # Total 1 unread left
    assert client.get("/api/notifications/unread-count", headers=headers).json()["unreadCount"] == 1

    # Mark all as read
    res_all = client.patch("/api/notifications/read-all", headers=headers)
    assert res_all.status_code == 200
    assert res_all.json()["success"] is True
    assert res_all.json()["modifiedCount"] == 1

    # Unread count is now 0
    assert client.get("/api/notifications/unread-count", headers=headers).json()["unreadCount"] == 0


def test_fcm_token_registration_and_removal(db):
    """Test register device token, update, and remove on logout."""
    user = _make_test_user(db, "fcm")
    user_id = user["id"]
    headers = {"Authorization": f"Bearer {user['token']}"}

    fcm_token_1 = f"fcm_test_token_1_{_uid()}"
    fcm_token_2 = f"fcm_test_token_2_{_uid()}"

    # Register token 1
    res1 = client.post("/api/notifications/devices", headers=headers, json={"fcmToken": fcm_token_1, "deviceType": "android"})
    assert res1.status_code == 200
    assert res1.json()["success"] is True

    # Register token 2 (multiple devices support)
    res2 = client.post("/api/notifications/devices", headers=headers, json={"fcmToken": fcm_token_2, "deviceType": "ios"})
    assert res2.status_code == 200

    token_col = get_device_token_collection(db)
    user_tokens = list(token_col.find({"userId": user_id}))
    assert len(user_tokens) == 2

    # Remove token 1 on logout
    del_res = client.request(
        "DELETE",
        "/api/notifications/devices",
        headers=headers,
        json={"fcmToken": fcm_token_1},
    )
    assert del_res.status_code == 200
    assert del_res.json()["modifiedCount"] == 1

    user_tokens_after = list(token_col.find({"userId": user_id}))
    assert len(user_tokens_after) == 1
    assert user_tokens_after[0]["fcmToken"] == fcm_token_2


def test_idempotent_notification_creation(db):
    """Creating notification with identical idempotencyKey prevents duplicates."""
    user = _make_test_user(db, "idempotency")
    key = f"key_{_uid()}"

    n1 = NotificationService.create_notification(
        db=db,
        recipient_user_id=user["id"],
        type=NotificationType.PAYMENT_SUCCESS,
        title="Payment Success",
        body="Payment verified.",
        idempotency_key=key,
        send_push=False,
    )
    assert n1 is not None

    n2 = NotificationService.create_notification(
        db=db,
        recipient_user_id=user["id"],
        type=NotificationType.PAYMENT_SUCCESS,
        title="Payment Success",
        body="Payment verified.",
        idempotency_key=key,
        send_push=False,
    )
    assert n2 is not None
    # Both returned references refer to the same notification document ID
    assert n1.id == n2.id

    notif_col = get_notification_collection(db)
    docs = list(notif_col.find({"idempotencyKey": key}))
    assert len(docs) == 1


def test_appointment_reminders_scheduling_and_idempotency(db):
    """Test 24h and 1h appointment reminders logic."""
    user = _make_test_user(db, "reminders")
    now_sl = datetime.now(SL_TIMEZONE)

    # 1. Create a confirmed appointment in 20 hours (within 24h window)
    appt_24h_time = now_sl + timedelta(hours=20)
    date_str_24h = appt_24h_time.strftime("%Y-%m-%d")
    time_str_24h = appt_24h_time.strftime("%H:%M")

    appt_24h = {
        "_id": ObjectId(),
        "patientUserId": user["id"],
        "doctorUserId": str(ObjectId()),
        "doctorProfileId": str(ObjectId()),
        "availabilityId": str(ObjectId()),
        "appointmentDate": date_str_24h,
        "startTime": time_str_24h,
        "endTime": "12:00",
        "status": AppointmentStatus.CONFIRMED.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
        "remindersSent": [],
    }
    db["appointments"].insert_one(appt_24h)

    # 2. Create a confirmed appointment in 30 minutes (within 1h window)
    appt_1h_time = now_sl + timedelta(minutes=30)
    date_str_1h = appt_1h_time.strftime("%Y-%m-%d")
    time_str_1h = appt_1h_time.strftime("%H:%M")

    appt_1h = {
        "_id": ObjectId(),
        "patientUserId": user["id"],
        "doctorUserId": str(ObjectId()),
        "doctorProfileId": str(ObjectId()),
        "availabilityId": str(ObjectId()),
        "appointmentDate": date_str_1h,
        "startTime": time_str_1h,
        "endTime": "12:00",
        "status": AppointmentStatus.CONFIRMED.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
        "remindersSent": [],
    }
    db["appointments"].insert_one(appt_1h)

    # 3. Create a cancelled appointment in 30 minutes (must NOT receive reminder)
    appt_cancelled = {
        "_id": ObjectId(),
        "patientUserId": user["id"],
        "doctorUserId": str(ObjectId()),
        "doctorProfileId": str(ObjectId()),
        "availabilityId": str(ObjectId()),
        "appointmentDate": date_str_1h,
        "startTime": time_str_1h,
        "endTime": "12:00",
        "status": AppointmentStatus.CANCELLED.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
        "remindersSent": [],
    }
    db["appointments"].insert_one(appt_cancelled)

    # Run reminder check
    sent_count = NotificationService.check_and_send_appointment_reminders(db)
    assert sent_count >= 2

    # Verify atomic remindersSent flag is set on appointments
    updated_24h = db["appointments"].find_one({"_id": appt_24h["_id"]})
    assert "24h" in updated_24h.get("remindersSent", [])

    updated_1h = db["appointments"].find_one({"_id": appt_1h["_id"]})
    assert "1h" in updated_1h.get("remindersSent", [])

    # Second execution must NOT duplicate reminders
    sent_count_again = NotificationService.check_and_send_appointment_reminders(db)
    # The appointments already have the flags, so 0 more reminders should be sent for them
    assert sent_count_again == 0


def test_push_delivery_failure_isolation(db):
    """Failure in FCM dispatch must never break notification persistence."""
    user = _make_test_user(db, "fcm_isolation")

    with patch.object(NotificationService, "_send_fcm_push", side_effect=Exception("FCM simulated network failure")):
        # Creating notification must still succeed and persist
        notif = NotificationService.create_notification(
            db=db,
            recipient_user_id=user["id"],
            type=NotificationType.SYSTEM,
            title="Safe Alert",
            body="Push failed but notification is saved.",
            send_push=True,
        )
        assert notif is not None
        assert notif.title == "Safe Alert"
