"""Helpers for writing Pydantic models to MongoDB (P04-N20)."""

from typing import Any, Dict

from pydantic import BaseModel


def document_for_insert(model: BaseModel) -> Dict[str, Any]:
    """Dump a model for insert_one without an explicit ``"_id": None``.

    Several models declare ``id: Optional[str] = Field(default=None, alias="_id")``. Dumping them with
    ``by_alias=True`` produced ``{"_id": None}``, so the first insert stored a document whose _id is null and every
    later insert into the same collection failed with a duplicate-key error. Without the key, MongoDB assigns an
    ObjectId.
    """
    doc = model.model_dump(by_alias=True)
    if doc.get("_id") is None:
        doc.pop("_id", None)
    return doc
