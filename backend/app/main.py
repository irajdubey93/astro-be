# app/main.py
from fastapi import FastAPI
from app.database import Base, engine
from app.models import *  # Ensure models are imported before create_all
from app.routes import auth, profile
from app.redis_client import init_redis, close_redis

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Astro App Backend")

# Routers
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(profile.router, prefix="", tags=["Profiles"])

# Redis startup/shutdown
@app.on_event("startup")
async def startup_event():
    await init_redis()

@app.on_event("shutdown")
async def shutdown_event():
    await close_redis()

    