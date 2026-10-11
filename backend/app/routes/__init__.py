from app.routes.admin import router as admin_router
from app.routes.appointment import appointment_router
from app.routes.auth import router as auth_router
from app.routes.doctor import doctor_router
from app.routes.notification import router as notification_router
from app.routes.payment import payment_router

__all__ = [
    "admin_router",
    "appointment_router",
    "auth_router",
    "doctor_router",
    "notification_router",
    "payment_router",
]
