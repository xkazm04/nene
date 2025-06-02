from routes.yt import router as yt_router
from routes.fc import router as fc_router
from routes.profile import router as profile_router
from fastapi import APIRouter

api_router = APIRouter()

api_router.include_router(yt_router, prefix="/yt", tags=["youtube"])
api_router.include_router(fc_router, prefix="/fc", tags=["fact-checking"])
api_router.include_router(profile_router, prefix="/profile", tags=["profiles"])