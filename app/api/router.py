"""
Aggregates all feature routers into a single top-level API router.

main.py imports only this one router. As new route modules are added
(e.g. app/api/reminders.py, app/api/resume.py in later steps), they're
wired in here — main.py never needs to change.
"""

from fastapi import APIRouter

from app.api.deadline import router as deadline_router
from app.api.auth import router as auth_router
from app.api.users import router as users_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(deadline_router)