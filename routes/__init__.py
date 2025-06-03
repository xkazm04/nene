from routes.yt import router as yt_router
from routes.fc import router as fc_router
from routes.profile import router as profile_router
from routes.videos import router as video_router
from routes.news import router as news_router
from routes.debug import router as debug_router

from fastapi import APIRouter

api_router = APIRouter()

api_router.include_router(yt_router, prefix="/yt", tags=["youtube"])
api_router.include_router(fc_router, prefix="/fc", tags=["fact-checking"])
api_router.include_router(profile_router, prefix="/profile", tags=["profiles"])
api_router.include_router(video_router, prefix="/videos", tags=["videos"])
api_router.include_router(news_router, prefix="/news", tags=["news"])
api_router.include_router(debug_router, prefix="/debug", tags=["debug"])