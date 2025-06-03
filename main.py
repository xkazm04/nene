from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import api_router
from config.logging_config import setup_logging

from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.backends.inmemory import InMemoryBackend
import redis.asyncio as redis
import os
from contextlib import asynccontextmanager

# Initialize logging at the start of your application
setup_logging(log_level="INFO", log_file="video_processing.log")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # Initialize cache backend
    try:
        # Try Redis first (recommended for production)
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis_client = redis.from_url(redis_url, encoding="utf8", decode_responses=True)
        await redis_client.ping()  # Test connection
        
        FastAPICache.init(
            RedisBackend(redis_client), 
            prefix="factchecker-cache"
        )
        print("✅ Cache initialized with Redis backend")
        
    except Exception as e:
        # Fallback to in-memory cache
        print(f"⚠️  Redis not available ({e}), using in-memory cache")
        FastAPICache.init(
            InMemoryBackend(), 
            prefix="factchecker-cache"
        )
    
    yield
    
    # Shutdown
    print("🔄 Shutting down cache...")

# Create FastAPI instance
app = FastAPI(
    title="FactChecker API",
    description="API for video fact-checking and analysis",
    version="1.0.0",
    lifespan=lifespan
)


app.include_router(
    api_router,
    prefix="",
    tags=["core"]
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Welcome to Nene API"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "nene-api"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)