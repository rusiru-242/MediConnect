"""Medicine label & packaging image analysis (BUG-023 / BUG-026).

What changed and why
--------------------
The previous implementation:
- "identified" medicines from the *file name* or prompt (``paracetamol_box.png``) without reading the image;
- called a retired Gemini model (``gemini-1.5-flash``) with the API key in the URL, synchronously
  inside the event loop, with a 6 s timeout; and
- when that call failed, returned the placeholder string ``"Generic Medicine Label"`` which was then
  shown to the patient as "Extracted Text".

This module now:
1. validates the upload (JPEG/PNG magic bytes, 5 MB limit);
2. sends the actual image bytes to the configured Vision provider (Gemini, else OpenAI) off the
   event loop, asking for structured JSON of *printed text only*;
3. separates text read from the image from verified MediConnect reference information;
4. reports truthful states: ``analyzed``, ``unreadable``, ``not_medicine``, ``provider_unavailable``,
   ``invalid_file`` — never a fabricated success;
5. never identifies loose tablets from appearance, and always recommends pharmacist verification.

Privacy: images are sent to the external provider only when ``AI_EXTERNAL_IMAGE_ANALYSIS_ENABLED``
is true (default true for development). The prompt instructs the model to omit personal details
(patient names, addresses). Production use requires an approved data-processing agreement — see
docs/SECURITY_AND_CLINICAL_SAFETY_REPORT.md.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

from app.agents.medicine_knowledge import MedicineKnowledge
from app.config.settings import settings

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png"}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
VISION_TIMEOUT_SECONDS = 25

MAGIC_BYTES = {
    "png": b"\x89PNG\r\n\x1a\n",
    "jpeg": b"\xff\xd8\xff",
}

PHARMACIST_NOTE_EN = ("Reading a photo cannot confirm that a medicine is genuine, in date, or right for you. "
                      "Check the package with a registered pharmacist or your doctor before use.")
PHARMACIST_NOTE_SI = ("ඡායාරූපයක් කියවීමෙන් ඖෂධය නිසි එකක්ද, කල් ඉකුත් වී නැද්ද, ඔබට ගැළපේද යන්න තහවුරු කළ නොහැක. "
                      "භාවිතයට පෙර ලියාපදිංචි ඖෂධවේදියෙකු හෝ වෛද්‍යවරයෙකු ලවා පරීක්ෂා කරගන්න.")

VISION_PROMPT = (
    "You are reading a photo for a pharmacy-safety assistant. Report ONLY text that is clearly printed and legible "
    "on the medicine packaging, label or blister strip. Do not guess, infer or complete partially visible words. "
    "Do NOT transcribe any personal information (patient names, addresses, phone numbers, prescription numbers). "
    "If the image shows loose tablets/capsules without readable printing, set loose_tablets_only=true and do not "
    "name a medicine. Respond with JSON only, matching this schema: "
    '{"is_medicine_packaging": boolean, "readable": boolean, "loose_tablets_only": boolean, '
    '"medicine_names": [string], "active_ingredients": [string], "strengths": [string], '
    '"dosage_form": string|null, "route": string|null, "legal_category": string|null, '
    '"expiry_date_visible": string|null, "manufacturer": string|null, "other_visible_text": [string], '
    '"image_quality": "good"|"blurry"|"partial"|"dark"}'
)


def validate_image_file_bytes(content: bytes, filename: str) -> Tuple[bool, Optional[str]]:
    """Validate file size, extension, and magic bytes."""
    if not content:
        return False, "Uploaded image file is empty."

    if len(content) > MAX_IMAGE_SIZE_BYTES:
        return False, f"Image size exceeds the maximum allowed limit of 5 MB ({len(content) // (1024*1024)} MB received)."

    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return False, f"Unsupported file type ({ext or 'none'}). Only JPG, JPEG, and PNG images are accepted."

    if ext == ".png" and not content.startswith(MAGIC_BYTES["png"]):
        return False, "File content does not match standard PNG format."
    if ext in {".jpg", ".jpeg"} and not content.startswith(MAGIC_BYTES["jpeg"]):
        return False, "File content does not match standard JPEG format."

    return True, None


class VisionUnavailable(Exception):
    """Raised when no vision provider is configured or the provider call failed."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _gemini_model_name() -> str:
    model = (settings.GEMINI_MODEL or "").removeprefix("models/").strip() or "gemini-flash-latest"
    # Retired / renamed model identifiers are mapped to the maintained alias.
    if model in {"gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro-vision", "gemini-2.5-flash"}:
        model = "gemini-flash-latest"
    return model


def _parse_json_payload(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?|```$", "", cleaned, flags=re.MULTILINE).strip()
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Vision response was not an object")
    return data


def _call_vision_provider(image_bytes: bytes, mime: str) -> Tuple[Dict[str, Any], str]:
    """Blocking provider call. Returns (structured_result, provider_name). Raises VisionUnavailable."""
    import requests

    if not getattr(settings, "AI_EXTERNAL_IMAGE_ANALYSIS_ENABLED", True):
        raise VisionUnavailable("disabled_by_configuration")
    encoded = base64.b64encode(image_bytes).decode("ascii")
    gemini_key = (settings.GEMINI_API_KEY or "").strip()
    openai_key = (settings.OPENAI_API_KEY or "").strip()
    if not gemini_key and not openai_key:
        raise VisionUnavailable("not_configured")
    try:
        if gemini_key:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{_gemini_model_name()}:generateContent"
            payload = {
                "contents": [{"parts": [{"text": VISION_PROMPT}, {"inline_data": {"mime_type": mime, "data": encoded}}]}],
                "generationConfig": {"temperature": 0, "responseMimeType": "application/json", "maxOutputTokens": 1024},
            }
            from app.agents.provider_gateway import ProviderCallError, send
            try:
                data = send("gemini", _gemini_model_name(), url, {"x-goog-api-key": gemini_key}, payload,
                            VISION_TIMEOUT_SECONDS)
            except ProviderCallError as exc:
                raise VisionUnavailable(f"gemini_{exc.category}")
            parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
            text = "".join(part.get("text", "") for part in parts if not part.get("thought"))
            return _parse_json_payload(text), "gemini"
        from app.agents.provider_gateway import ProviderCallError, send
        try:
            data = send("openai", settings.OPENAI_MODEL, "https://api.openai.com/v1/chat/completions",
                        {"Authorization": f"Bearer {openai_key}"}, {
                "model": settings.OPENAI_MODEL,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": VISION_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
                ]}],
                "max_completion_tokens": 1024,
            }, VISION_TIMEOUT_SECONDS)
        except ProviderCallError as exc:
            raise VisionUnavailable(f"openai_{exc.category}")
        content = data["choices"][0]["message"].get("content") or ""
        return _parse_json_payload(content), "openai"
    except VisionUnavailable:
        raise
    except (ValueError, KeyError, IndexError) as exc:
        raise VisionUnavailable(f"invalid_response:{type(exc).__name__}") from exc
    except Exception as exc:  # network errors, timeouts
        raise VisionUnavailable(f"request_failed:{type(exc).__name__}") from exc


def _clean_list(values: Any, limit: int = 6) -> List[str]:
    if not isinstance(values, list):
        values = [values] if isinstance(values, str) else []
    cleaned = []
    for value in values:
        if isinstance(value, str):
            text = re.sub(r"\s+", " ", value).strip()[:120]
            if text and text.lower() not in {"null", "none", "n/a", "unknown"}:
                cleaned.append(text)
    return cleaned[:limit]


def _clean_text(value: Any) -> Optional[str]:
    items = _clean_list([value] if isinstance(value, str) else [], 1)
    return items[0] if items else None


def _uncertain(status: str, text: str, explanation: str, advice: str, clearer: bool, **extra) -> Dict[str, Any]:
    return {
        "success": status == "analyzed",
        "status": status,
        "text": text,
        "analysis": {
            "status": status,
            "detectedText": None,
            "identifiedMedicine": None,
            "confidenceLevel": "unidentified" if status in {"provider_unavailable", "invalid_file", "not_medicine"} else "low",
            "uncertaintyExplanation": explanation,
            "safetyAdvice": advice,
            "requiresClearerPhoto": clearer,
            **extra,
        },
        "medicineCard": None,
    }


class MedicineImageAgent:
    """Agent for safe interpretation of medicine labels and packaging."""

    @classmethod
    async def analyze_medicine_image(
        cls,
        image_bytes: bytes,
        filename: str,
        user_prompt: Optional[str] = None,
        lang: str = "en",
    ) -> Dict[str, Any]:
        si = lang == "si"
        is_valid, error_msg = validate_image_file_bytes(image_bytes, filename)
        if not is_valid:
            return _uncertain(
                "invalid_file",
                f"**Upload error:** {error_msg}" if not si else f"**උඩුගත කිරීමේ දෝෂයකි:** {error_msg}",
                error_msg or "Invalid image file.",
                "Please upload a JPEG or PNG photo under 5 MB.",
                True,
            )

        mime = "image/png" if Path(filename).suffix.lower() == ".png" else "image/jpeg"
        try:
            extracted, provider = await asyncio.wait_for(
                asyncio.to_thread(_call_vision_provider, image_bytes, mime), timeout=VISION_TIMEOUT_SECONDS + 5,
            )
        except (VisionUnavailable, asyncio.TimeoutError) as exc:
            reason = getattr(exc, "reason", "timeout")
            logger.warning("Medicine image analysis unavailable: %s", reason)
            return _uncertain(
                "provider_unavailable",
                ("**Image received, but it could not be analysed right now.**\n\n"
                 "The image-reading service is unavailable, so I have not read anything from your photo. "
                 "Please try again later, or type the medicine name printed on the package.\n\n" + PHARMACIST_NOTE_EN)
                if not si else
                ("**පින්තූරය ලැබුණා, නමුත් දැන් එය විශ්ලේෂණය කළ නොහැක.**\n\n"
                 "පින්තූර කියවීමේ සේවාව දැනට ලබාගත නොහැකි නිසා මම ඔබේ පින්තූරයෙන් කිසිවක් කියවා නැහැ. "
                 "පසුව නැවත උත්සාහ කරන්න, නැතහොත් පැකේජයේ මුද්‍රණය කර ඇති ඖෂධ නාමය ටයිප් කරන්න.\n\n" + PHARMACIST_NOTE_SI),
                f"Vision provider unavailable ({reason}).",
                "Do not rely on this result. Ask a pharmacist to check the package.",
                False,
                providerError=reason,
            )

        is_packaging = bool(extracted.get("is_medicine_packaging"))
        readable = bool(extracted.get("readable"))
        loose = bool(extracted.get("loose_tablets_only"))
        names = _clean_list(extracted.get("medicine_names"))
        ingredients = _clean_list(extracted.get("active_ingredients"))
        strengths = _clean_list(extracted.get("strengths"))
        fields = {
            "medicineNames": names,
            "activeIngredients": ingredients,
            "strengths": strengths,
            "dosageForm": _clean_text(extracted.get("dosage_form")),
            "route": _clean_text(extracted.get("route")),
            "legalCategory": _clean_text(extracted.get("legal_category")),
            "expiryDateVisible": _clean_text(extracted.get("expiry_date_visible")),
            "manufacturer": _clean_text(extracted.get("manufacturer")),
            "otherVisibleText": _clean_list(extracted.get("other_visible_text"), 8),
            "imageQuality": _clean_text(extracted.get("image_quality")),
        }

        if loose:
            return _uncertain(
                "unreadable",
                ("**Loose tablets or capsules can't be identified safely from a photo.**\n\n"
                 "- Do not take a tablet you cannot identify from its original labelled package.\n"
                 "- Take the tablets and any packaging to a registered pharmacist.\n" + PHARMACIST_NOTE_EN)
                if not si else
                ("**ලේබල් නැති පෙති හෝ කැප්සියුල ඡායාරූපයකින් ආරක්ෂිතව හඳුනාගත නොහැක.**\n\n"
                 "- මුල් ලේබලය සහිත පැකේජයෙන් හඳුනාගත නොහැකි පෙත්තක් ගන්න එපා.\n"
                 "- පෙති සහ ඇසුරුම ලියාපදිංචි ඖෂධවේදියෙකු වෙත රැගෙන යන්න.\n" + PHARMACIST_NOTE_SI),
                "Loose tablets without legible printing cannot be identified from appearance.",
                "Never take an unidentified tablet. Ask a pharmacist.",
                True, provider=provider, extracted=fields,
            )
        if not is_packaging:
            return _uncertain(
                "not_medicine",
                ("**This doesn't look like a medicine package or label.** Please upload a clear photo of the medicine box, "
                 "bottle label or blister strip with the printed name visible.")
                if not si else
                "**මෙය ඖෂධ පැකේජයක් හෝ ලේබලයක් ලෙස නොපෙනේ.** ඖෂධ නාමය පැහැදිලිව පෙනෙන පරිදි පැකේජයේ ඡායාරූපයක් එවන්න.",
                "The uploaded image does not appear to show medicine packaging.",
                "Upload a photo of the medicine packaging or label.",
                True, provider=provider,
            )
        if not readable or not (names or ingredients):
            return _uncertain(
                "unreadable",
                ("**Medicine packaging analysis — text not readable**\n\n"
                 "I couldn't read the medicine name clearly. Please take a sharper, well-lit, close-up photo of the "
                 "printed name and strength.\n\n- Do not take a medicine you cannot identify.\n" + PHARMACIST_NOTE_EN)
                if not si else
                ("**ඖෂධ පැකේජ විශ්ලේෂණය — අකුරු කියවිය නොහැක**\n\n"
                 "ඖෂධ නාමය පැහැදිලිව කියවිය නොහැකි විය. නම සහ ප්‍රබලතාව පැහැදිලිව පෙනෙන, හොඳ ආලෝකයක් ඇති ඡායාරූපයක් එවන්න.\n\n"
                 "- හඳුනාගත නොහැකි ඖෂධයක් ගන්න එපා.\n" + PHARMACIST_NOTE_SI),
                "Label text is unreadable, blurry or partially hidden.",
                "Never consume an unverified or unidentified medicine. Bring packaging to a pharmacist.",
                True, provider=provider, extracted=fields,
            )

        read_lines = []
        labels = [("Name", ", ".join(names)), ("Active ingredient", ", ".join(ingredients)),
                  ("Strength", ", ".join(strengths)), ("Form", fields["dosageForm"]), ("Route", fields["route"]),
                  ("Category", fields["legalCategory"]), ("Expiry shown", fields["expiryDateVisible"])]
        for label, value in labels:
            if value:
                read_lines.append(f"- {label}: {value}")
        detected_text = "; ".join(f"{label}: {value}" for label, value in labels if value)

        match = MedicineKnowledge.find_medicine(" ".join(names + ingredients))
        header = "**Text read from your photo** (as printed — not verified):" if not si else "**ඔබේ ඡායාරූපයෙන් කියවූ අකුරු** (මුද්‍රිත ආකාරයට — තහවුරු කර නැත):"
        parts = [header, *read_lines, ""]
        card = None
        if match:
            parts += [
                "**Reference information from the MediConnect medicine library:**" if not si else "**MediConnect ඖෂධ පුස්තකාලයේ තොරතුරු:**",
                f"- {match['genericName']} — {match['drugClass']}",
                f"- Common uses: {', '.join(match['commonUses'][:2])}",
            ]
            if match.get("isPrescriptionRequired"):
                parts.append("- Prescription medicine: use only as prescribed by your doctor.")
            card = {
                "medicineName": match["genericName"],
                "activeIngredient": match["activeIngredient"],
                "formulations": list(match.get("formulations") or []),
                "contentReviewStatus": "PENDING_PHARMACIST_REVIEW",
                "commonUses": match["commonUses"],
                "precautions": match["precautions"],
                "sideEffects": match["sideEffects"],
                "warnings": match["warnings"],
                "consultPharmacistWhen": match["consultPharmacistWhen"],
                "isPrescriptionRequired": match["isPrescriptionRequired"],
            }
        else:
            parts.append("This medicine is not in the MediConnect reference library yet, so I can't add verified details."
                         if not si else "මෙම ඖෂධය MediConnect පුස්තකාලයේ තවම නැති නිසා තහවුරු කළ තොරතුරු එක් කළ නොහැක.")
        parts += ["", "The strength on a package is not a dose recommendation." if not si else
                  "පැකේජයේ ඇති ප්‍රබලතාව මාත්‍රා නිර්දේශයක් නොවේ.", PHARMACIST_NOTE_SI if si else PHARMACIST_NOTE_EN]

        return {
            "success": True,
            "status": "analyzed",
            "text": "\n".join(parts),
            "analysis": {
                "status": "analyzed",
                "provider": provider,
                "detectedText": detected_text,
                "extracted": fields,
                "identifiedMedicine": match["genericName"] if match else None,
                "activeIngredient": match["activeIngredient"] if match else (", ".join(ingredients) or None),
                "confidenceLevel": "moderate" if match else "low",
                "uncertaintyExplanation": (
                    "Printed label text was read from the image and matched to the reference library. A photo cannot "
                    "verify authenticity, storage or expiry." if match else
                    "Printed label text was read from the image but is not in the reference library."
                ),
                "safetyAdvice": "Confirm with a pharmacist or your prescribing doctor before use.",
                "requiresClearerPhoto": False,
            },
            "medicineCard": card,
        }
