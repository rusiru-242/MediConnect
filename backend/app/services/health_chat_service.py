"""Service managing AI Health Chat session lifecycle, authorization, and message handling."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.agents.health_assistant_agent import HealthAssistantAgent
from app.models.health_chat import (
    HealthChatSessionDocument,
    TriageLevel,
    get_health_chat_collection,
    utc_now,
)
from app.schemas.health_chat import (
    CreateHealthChatSessionRequest,
    DeleteHealthChatSessionResponse,
    DoctorReferralCardSchema,
    HealthChatMessageResponse,
    HealthChatSessionResponse,
    SendHealthChatMessageRequest,
)
from app.schemas.user import UserResponseSchema

logger = logging.getLogger(__name__)


def _to_response_schema(doc: Dict[str, Any]) -> HealthChatSessionResponse:
    """Map MongoDB health chat session document to Pydantic response schema."""
    session_id = str(doc.get("_id") or doc.get("id"))
    patient_user_id = str(doc.get("patientUserId"))

    messages: List[HealthChatMessageResponse] = []
    for m in doc.get("messages", []):
        metadata = m.get("metadata") or {}
        referrals = [
            DoctorReferralCardSchema(**ref) for ref in metadata.get("doctorReferrals", [])
        ]
        messages.append(
            HealthChatMessageResponse(
                id=str(m.get("id", ObjectId())),
                sender=m.get("sender", "assistant"),
                content=m.get("content", ""),
                timestamp=m.get("timestamp", utc_now()),
                triageLevel=metadata.get("triageLevel"),
                isUrgent=bool(metadata.get("isUrgent", False)),
                emergencyNumber=metadata.get("emergencyNumber"),
                disclaimer=metadata.get("disclaimer"),
                clarifyingQuestions=metadata.get("clarifyingQuestions", []),
                recommendedSpecialty=metadata.get("recommendedSpecialty"),
                doctorReferrals=referrals,
                metadata=metadata,
            )
        )

    return HealthChatSessionResponse(
        id=session_id,
        patientUserId=patient_user_id,
        language=doc.get("language", "en"),
        consentGiven=bool(doc.get("consentGiven", True)),
        triageLevel=doc.get("triageLevel"),
        recommendedSpecialty=doc.get("recommendedSpecialty"),
        messages=messages,
        createdAt=doc.get("createdAt", utc_now()),
        updatedAt=doc.get("updatedAt", utc_now()),
        expiresAt=doc.get("expiresAt", utc_now()),
    )


class HealthChatService:
    """Service layer managing patient health assistant chat sessions."""

    @classmethod
    async def create_session(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        req: CreateHealthChatSessionRequest,
    ) -> HealthChatSessionResponse:
        """Create a new health guidance chat session for the authenticated patient."""
        collection = get_health_chat_collection(db)
        patient_id_str = str(patient_user.id)
        now = utc_now()

        session_model = HealthChatSessionDocument(
            patientUserId=patient_id_str,
            language=req.language or "en",
            consentGiven=req.consentGiven,
            triageLevel=TriageLevel.GENERAL_INFO.value,
            createdAt=now,
            updatedAt=now,
        )
        session_dict = session_model.to_mongo_dict()

        if req.initialMessage and req.initialMessage.strip():
            session_dict = await HealthAssistantAgent.process_user_turn(
                db=db,
                session_data=session_dict,
                user_message=req.initialMessage.strip(),
                language_override=req.language,
            )
        else:
            # Welcoming educational greeting
            lang = req.language or "en"
            if lang == "si":
                greeting = (
                    "ආයුබෝවන්! මම MediConnect AI සෞඛ්‍ය සහායකයා වෙමි. "
                    "ඔබගේ රෝග ලක්ෂණ පිළිබඳ සාමාන්‍ය තොරතුරු දැනගැනීමට සහ සුදුසුකම් ලත් වෛද්‍යවරුන් සොයා ගැනීමට ඔබට මට සහාය විය හැක.\n\n"
                    "අද දින ඔබට ඇති අපහසුතාවය කුමක්ද? (කරුණාකර මතක තබා ගන්න: මම රෝග විනිශ්චය හෝ ඖෂධ ලබා නොදෙමි.)"
                )
            else:
                greeting = (
                    "Hello! I am your MediConnect AI Health Assistant. "
                    "I can help explain common symptoms and guide you to verified medical doctors for an in-person assessment.\n\n"
                    "What symptoms or health questions would you like to explore today? "
                    "(Note: I provide educational guidance, not medical diagnoses or prescriptions.)"
                )

            session_dict["messages"] = [
                {
                    "id": str(ObjectId()),
                    "sender": "assistant",
                    "content": greeting,
                    "timestamp": now,
                    "metadata": {
                        "type": "welcome",
                        "triageLevel": TriageLevel.GENERAL_INFO.value,
                        "disclaimer": (
                            "MediConnect provides general health guidance only. Always consult a licensed doctor."
                        ),
                    },
                }
            ]

        res = collection.insert_one(session_dict)
        session_dict["_id"] = res.inserted_id
        logger.info("Created health chat session %s for patient %s", str(res.inserted_id), patient_id_str)
        return _to_response_schema(session_dict)

    @classmethod
    async def get_session(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        session_id: str,
    ) -> HealthChatSessionResponse:
        """Retrieve a session by ID ensuring patient ownership."""
        doc = cls._get_session_or_404(db, patient_user, session_id)
        return _to_response_schema(doc)

    @classmethod
    async def send_message(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        session_id: str,
        req: SendHealthChatMessageRequest,
    ) -> HealthChatSessionResponse:
        """Process an incoming message and append conversational guidance."""
        doc = cls._get_session_or_404(db, patient_user, session_id)
        collection = get_health_chat_collection(db)

        updated_dict = await HealthAssistantAgent.process_user_turn(
            db=db,
            session_data=doc,
            user_message=req.message,
            language_override=req.language,
        )

        collection.replace_one({"_id": doc["_id"]}, updated_dict)
        return _to_response_schema(updated_dict)

    @classmethod
    async def delete_session(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        session_id: str,
    ) -> DeleteHealthChatSessionResponse:
        """Permanently delete a health guidance session for patient privacy."""
        doc = cls._get_session_or_404(db, patient_user, session_id)
        collection = get_health_chat_collection(db)

        collection.delete_one({"_id": doc["_id"]})
        logger.info("Deleted health chat session %s for patient %s", session_id, str(patient_user.id))
        return DeleteHealthChatSessionResponse(
            success=True,
            message="Health chat session permanently deleted.",
        )

    @classmethod
    def _get_session_or_404(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        session_id: str,
    ) -> Dict[str, Any]:
        """Fetch session and strictly enforce patient ownership."""
        collection = get_health_chat_collection(db)
        if not ObjectId.is_valid(session_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Health chat session not found.",
            )

        doc = collection.find_one({"_id": ObjectId(session_id)})
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Health chat session not found.",
            )

        if str(doc.get("patientUserId")) != str(patient_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this health chat session.",
            )

        return doc
