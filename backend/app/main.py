from fastapi import FastAPI
from app.database import Base, engine
from app.routes import auth, profile

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Astro App Backend")

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(profile.router, prefix="", tags=["Profiles"])