from routes.yt import router as yt_router
from routes.fc import router as fc_router
from routes.profile import router as profile_router
from routes.videos import router as video_router
from routes.news import router as news_router
from routes.debug import router as debug_router
from routes.top.top_items import router as top_item_router
from routes.top.top_lists import router as top_list_router
from routes.top.top_users import router as top_user_router
from routes.top.top_item_research import router as item_research_router

from fastapi import APIRouter

api_router = APIRouter()

api_router.include_router(yt_router, prefix="/yt", tags=["youtube"])
api_router.include_router(fc_router, prefix="/fc", tags=["fact-checking"])
api_router.include_router(profile_router, prefix="/profile", tags=["profiles"])
api_router.include_router(video_router, prefix="/videos", tags=["videos"])
api_router.include_router(news_router, prefix="/news", tags=["news"])
api_router.include_router(debug_router, prefix="/debug", tags=["debug"])
api_router.include_router(top_item_router, prefix="/top/items", tags=["top-lists"])
api_router.include_router(top_list_router, prefix="/top/lists", tags=["top-lists"])
api_router.include_router(top_user_router, prefix="/top/users", tags=["top-lists"])
api_router.include_router(item_research_router, prefix="/top/research", tags=["item-research"])

