from app.routes.admin import router as admin_router
from app.routes.ai_booking import ai_booking_router
from app.routes.ai_health_chat import ai_health_chat_router
from app.routes.ai_recommendations import router as ai_recommendations_router
from app.routes.appointment import appointment_router
from app.routes.auth import router as auth_router
from app.routes.doctor import doctor_router
from app.routes.medical_record import medical_record_router
from app.routes.medication_reminder import medication_reminder_router
from app.routes.notification import router as notification_router
from app.routes.payment import payment_router
from app.routes.prescription import prescription_router

__all__ = [
    "admin_router",
    "ai_booking_router",
    "ai_health_chat_router",
    "ai_recommendations_router",
    "appointment_router",
    "auth_router",
    "doctor_router",
    "medical_record_router",
    "medication_reminder_router",
    "notification_router",
    "payment_router",
    "prescription_router",
]


