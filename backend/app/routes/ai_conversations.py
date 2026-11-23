"""Persistent history for the existing AI booking assistant."""

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, StringConstraints
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from typing import Annotated

from app.config.database import get_database
from app.middleware.auth import require_patient
from app.models.booking_session import get_booking_session_collection, utc_now
from app.routes.ai_booking import _check_rate_limit
from app.schemas.booking_session import ChatMessageSchema, CreateSessionRequest, SendMessageRequest
from app.services.booking_session_service import BookingSessionService

router = APIRouter(prefix="/ai/conversations", tags=["AI conversations"])


class RenameConversation(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class ConversationMessages(BaseModel):
    messages: list[ChatMessageSchema]
    nextBefore: int | None


def _owner(user):
    return {"patientUserId": str(user.id), "persistent": True}


def _conversation(user, conversation_id):
    if not ObjectId.is_valid(conversation_id):
        raise HTTPException(400, "Invalid conversation ID.")
    return {**_owner(user), "_id": ObjectId(conversation_id)}


def _summary(doc):
    return {
        "id": str(doc["_id"]),
        "title": doc["title"],
        "preview": doc.get("preview", ""),
        "status": doc["state"],
        "updatedAt": doc["updatedAt"],
        "createdAt": doc["createdAt"],
    }


@router.post("", status_code=201)
async def create(req: CreateSessionRequest, user=Depends(require_patient), db=Depends(get_database)):
    _check_rate_limit(str(user.id))
    collection = get_booking_session_collection(db)
    if not req.initialMessage:
        existing = collection.find_one({**_owner(user), "draft": True})
        if existing:
            return await BookingSessionService.get_session(db, user, str(existing["_id"]))
    try:
        return await BookingSessionService.create_session(db, user, req, persistent=True)
    except DuplicateKeyError:
        existing = collection.find_one({**_owner(user), "draft": True})
        if not existing:
            raise HTTPException(409, "The conversation changed. Please retry.")
        return await BookingSessionService.get_session(db, user, str(existing["_id"]))


@router.get("")
def list_conversations(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10000),
    user=Depends(require_patient),
    db=Depends(get_database),
):
    docs = get_booking_session_collection(db).find(_owner(user), {"messages": 0})
    return [_summary(doc) for doc in docs.sort([("updatedAt", -1), ("_id", -1)]).skip(offset).limit(limit)]


@router.get("/{conversation_id}/messages", response_model=ConversationMessages)
def messages(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=100),
    before: int | None = Query(None, ge=0),
    user=Depends(require_patient),
    db=Depends(get_database),
):
    doc = get_booking_session_collection(db).find_one(_conversation(user, conversation_id), {"messages": 1})
    if not doc:
        raise HTTPException(404, "Conversation not found.")
    transcript = doc["messages"]
    end = len(transcript) if before is None else min(before, len(transcript))
    start = max(0, end - limit)
    return {"messages": transcript[start:end], "nextBefore": start or None}


@router.post("/{conversation_id}/messages")
async def send(conversation_id: str, req: SendMessageRequest, user=Depends(require_patient), db=Depends(get_database)):
    _check_rate_limit(str(user.id))
    if req.imageUrl:
        raise HTTPException(422, "Upload images using the assistant's image endpoint.")
    if not get_booking_session_collection(db).find_one(_conversation(user, conversation_id), {"_id": 1}):
        raise HTTPException(404, "Conversation not found.")
    return await BookingSessionService.handle_message(db, user, conversation_id, req)


@router.patch("/{conversation_id}")
def rename(conversation_id: str, req: RenameConversation, user=Depends(require_patient), db=Depends(get_database)):
    query = _conversation(user, conversation_id)
    collection = get_booking_session_collection(db)
    doc = collection.find_one_and_update(
        {**query, "confirmationUntil": {"$not": {"$gt": utc_now()}}},
        {"$set": {"title": req.title, "updatedAt": utc_now(), "draft": False},
         "$inc": {"revision": 1}},
        return_document=ReturnDocument.AFTER,
    )
    if not doc:
        if collection.find_one(query, {"_id": 1}):
            raise HTTPException(409, "A booking update is in progress. Please retry.")
        raise HTTPException(404, "Conversation not found.")
    return _summary(doc)


@router.delete("/{conversation_id}", status_code=204)
def delete(conversation_id: str, user=Depends(require_patient), db=Depends(get_database)):
    query = _conversation(user, conversation_id)
    collection = get_booking_session_collection(db)
    result = collection.delete_one({**query, "confirmationUntil": {"$not": {"$gt": utc_now()}}})
    if not result.deleted_count:
        if collection.find_one(query, {"_id": 1}):
            raise HTTPException(409, "A booking update is in progress. Please retry.")
        raise HTTPException(404, "Conversation not found.")
    return Response(status_code=204)
