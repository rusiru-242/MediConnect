from app.routes.admin import router as admin_router
from app.routes.auth import router as auth_router
from app.routes.doctor import doctor_router

__all__ = ["admin_router", "auth_router", "doctor_router"]
