# Routers package
from app.routers.auth import router as auth_router
from app.routers.products import router as products_router
from app.routers.inspections import router as inspections_router
from app.routers.rules import router as rules_router
from app.routers.reports import router as reports_router
from app.routers.dashboard import router as dashboard_router
from app.routers.history import router as history_router

__all__ = [
    "auth_router",
    "products_router",
    "inspections_router",
    "rules_router",
    "reports_router",
    "dashboard_router",
    "history_router",
]
