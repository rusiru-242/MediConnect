"""Agent 17 — prescription assistant replies (A04). Deterministic and grounded in stored prescriptions only.

The assistant reads prescriptions through the role-checked tools (``get_my_prescriptions``,
``get_authorized_patient_prescriptions``) and formats exactly what the prescriber wrote. It never prescribes,
completes a dose, approves, signs, renews or changes a prescription: those requests get a refusal that names who
decides and where. A missing value is shown as "not stated", never filled in.
"""
import re
from datetime import datetime

from bson import ObjectId

from app.agents.orchestrator import AIOrchestrator
from app.services.clinical_safety_service import ClinicalSafetyService

RX_REFERENCE = re.compile(r"\bRX-(?:REN-)?\d{8}-[A-F0-9]{6}\b", re.I)
NOT_STATED = "not stated"

PATIENT_ACTION_REFUSAL = (
    "I can't approve, sign, finalize or renew a prescription, and I can't change one. Only your doctor can, after "
    "reviewing it. To ask for a renewal, open Medical Records and choose Prescription renewals; your doctor decides."
)
PATIENT_PRIVACY_REFUSAL = (
    "I can only show and discuss your own prescriptions. Another person's prescriptions are visible only to them "
    "and their doctors, and I can't change anyone's medicine or dose."
)
DOCTOR_ACTION_REFUSAL = (
    "The assistant cannot prescribe, approve, sign, finalize, renew or change a prescription or a dose. You do that "
    "yourself: issue or amend a prescription from the consultation screen after reviewing it, and decide renewals on "
    "the Renewals screen."
)
DOCTOR_DRAFT_HELP = (
    "The assistant does not write doses or fill in a prescription for you. Enter the medicines on the consultation "
    "form. Before you confirm, the review lists what you typed: missing required fields (name, strength, dose, "
    "frequency, duration, quantity), medicines entered twice, matches with documented allergies and with active "
    "prescriptions. Nothing is issued until you choose Confirm & Issue. Drug-interaction checking is not available."
)


def _date(value):
    if isinstance(value, datetime):
        return value.strftime("%d %b %Y")
    return str(value)[:10] if value else NOT_STATED


def item_line(item):
    """One medication item exactly as prescribed; absent values say so instead of being filled in."""
    value = lambda key: item.get(key) or NOT_STATED  # noqa: E731
    line = (f"{value('medicationName')} {item.get('strength') or ''}".strip()
            + f" — dose {value('dose')}, {item.get('route') or 'route ' + NOT_STATED}, {value('frequency')}, "
              f"for {value('duration')}, quantity {value('quantity')}")
    if item.get("additionalInstructions"):
        line += f". {item['additionalInstructions']}"
    return line


def prescription_text(rx):
    doctor = rx.get("doctorName")
    head = (f"{rx.get('prescriptionId')} · issued {_date(rx.get('issuedAt'))}"
            + (f" by Dr. {doctor.removeprefix('Dr. ')}" if doctor else "") + f" · {rx.get('status')}")
    lines = [head] + [f"  {index}. {item_line(item)}" for index, item in enumerate(rx.get("medicationItems") or [], 1)]
    if rx.get("instructions"):
        lines.append(f"  Doctor's instructions: {rx['instructions']}")
    return "\n".join(lines)


def list_text(rows, empty):
    if not rows:
        return empty
    return "\n\n".join(prescription_text(rx) for rx in rows)


# --------------------------------------------------------------------------------------------- patient chat
async def patient_reply(db, user, intent):
    """Return (text, metadata) for a patient prescription intent, or None when the intent is not one of ours."""
    if intent == "other_patient_prescriptions":
        return PATIENT_PRIVACY_REFUSAL, {"type": "prescription_privacy_refusal", "dataReturned": False}
    if intent == "prescription_authorization_request":
        return PATIENT_ACTION_REFUSAL, {"type": "prescription_action_requires_clinician", "changed": False}
    if intent not in {"my_prescriptions", "renewal_request"}:
        return None
    if user is None:
        return ("Sign in to see the prescriptions your doctors issued on MediConnect.",
                {"type": "prescriptions_sign_in_required"})
    result = await AIOrchestrator(db, user, None).execute("get_my_prescriptions", {}, {"get_my_prescriptions"})
    if "error" in result:
        return ("I could not read your prescriptions just now. Open Medical Records to see them.",
                {"type": "prescriptions_unavailable"})
    rows = result["prescriptions"]
    references = [rx.get("prescriptionId") for rx in rows]
    if intent == "my_prescriptions":
        text = list_text(rows, "You have no current prescriptions on MediConnect. Prescriptions from other clinics "
                               "are not shown.")
        if rows:
            text = ("Your current prescriptions, as your doctors wrote them:\n\n" + text
                    + "\n\nAsk the prescribing doctor or a pharmacist if any instruction is unclear.")
        return text, {"type": "my_prescriptions", "source": "prescriptions", "prescriptionIds": references}
    text = ("I don't submit or approve renewals from chat. Open Medical Records, choose Prescription renewals and "
            "select the medicine; the doctor who prescribed it approves or declines the request.")
    if rows:
        names = sorted({item.get("medicationName") for rx in rows for item in rx.get("medicationItems") or []
                        if item.get("medicationName")})
        text += " Medicines on your current prescriptions: " + ", ".join(names) + "."
    else:
        text += " You have no current prescription on MediConnect to renew."
    renewals = await AIOrchestrator(db, user, None).execute("get_my_renewal_requests", {}, {"get_my_renewal_requests"})
    labels = {"requested": "waiting for your doctor", "awaiting_review": "waiting for your doctor",
              "approved": "approved by your doctor", "rejected": "not approved by your doctor",
              "needs_consultation": "your doctor asked for a consultation", "cancelled": "cancelled"}
    recent = (renewals.get("renewals") or [])[:5] if "error" not in renewals else []
    if recent:
        text += "\n\nYour recent renewal requests:\n" + "\n".join(
            f"- {r.get('medicationName')} ({r.get('renewalId')}): {labels.get(r.get('status'), r.get('status'))}"
            for r in recent)
    return text, {"type": "prescription_renewal_guidance", "route": "/patient/prescription-renewals",
                  "renewalCreated": False, "prescriptionIds": references,
                  "renewalIds": [r.get("renewalId") for r in recent]}


# --------------------------------------------------------------------------------------------- doctor assistant
DOCTOR_PRESCRIPTION_INTENTS = frozenset({"prescription_action_request", "prescription_draft_help",
                                         "prescription_summary", "patient_prescriptions"})
OTHER_PATIENT = re.compile(r"\b(?:another|other|different|someone else'?s?)\s+patient", re.I)


async def doctor_reply(db, user, intent, message, appointment_id, owned_appointment):
    """Return the doctor-assistant response for a prescription intent, or None."""
    if intent not in DOCTOR_PRESCRIPTION_INTENTS:
        return None
    if intent == "prescription_action_request":
        return {"message": DOCTOR_ACTION_REFUSAL, "intent": intent, "refused": True}
    if intent == "prescription_draft_help":
        return {"message": DOCTOR_DRAFT_HELP, "intent": intent, "interactionCheck": "unavailable"}
    reference = RX_REFERENCE.search(message or "")
    if intent == "prescription_summary" and reference:
        rx = db["prescriptions"].find_one({"prescriptionId": reference.group(0).upper()})
        allowed = bool(rx) and (rx.get("doctorUserId") == str(user.id) or _has_care_relationship(db, user, rx))
        if not allowed:  # unknown and unauthorized look the same
            return {"message": "I could not find that prescription among your patients' prescriptions.",
                    "intent": intent}
        row = _row(db, rx)
        return {"message": "Summary of the prescription as written (not a clinical review):\n\n" + prescription_text(row),
                "intent": intent, "source": "prescriptions", "prescriptionId": row["prescriptionId"]}
    if OTHER_PATIENT.search(message or "") or not appointment_id:
        return {"message": "Select the patient's appointment first. I show prescriptions only for a patient you are "
                           "treating, one patient at a time.", "intent": intent}
    appointment = owned_appointment(db, user, appointment_id)
    patient_id = str(appointment["patientUserId"])
    result = await AIOrchestrator(db, user, None).execute(
        "get_authorized_patient_prescriptions", {"patient_id": patient_id}, {"get_authorized_patient_prescriptions"})
    if "error" in result:
        return {"message": "I could not retrieve this patient's prescriptions.", "intent": intent}
    rows = result["prescriptions"]
    if intent == "prescription_summary":  # "summarize this prescription" with a visit selected: that visit's
        rows = [rx for rx in rows if db["prescriptions"].find_one(
            {"_id": ObjectId(rx["_id"]), "appointmentId": appointment_id}, {"_id": 1})]
        empty = "No current prescription is recorded for this visit."
        intro = "Prescriptions written for this visit (not a clinical review):\n\n"
    else:
        empty = "No current prescription is recorded on MediConnect for this patient; medicines from elsewhere are not shown."
        intro = "This patient's current prescriptions on MediConnect:\n\n"
    return {"message": intro + list_text(rows, "") if rows else empty, "intent": intent, "source": "prescriptions",
            "prescriptionIds": [rx.get("prescriptionId") for rx in rows], "tool": "get_authorized_patient_prescriptions"}


def _has_care_relationship(db, user, rx):
    try:
        ClinicalSafetyService.verify_doctor_patient_care_relationship(db, str(user.id), rx["patientUserId"])
        return True
    except Exception:
        return False


def _row(db, rx):
    from app.agents.tool_registry import _prescription_rows
    rows = {row["_id"]: row for row in _prescription_rows(db, rx["patientUserId"])}
    if str(rx["_id"]) in rows:
        return rows[str(rx["_id"])]
    return {"prescriptionId": rx.get("prescriptionId"), "status": rx.get("status"), "issuedAt": rx.get("issuedAt"),
            "medicationItems": rx.get("medicationItems") or [], "instructions": rx.get("instructions")}
