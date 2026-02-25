import logging

import coloredlogs
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .db.database import init_db

coloredlogs.install(
    level=logging.INFO,
    fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Suppress google_genai AFC info logs
logging.getLogger("google_genai.models").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Workshop — Jewelry Style Generator", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# V1 personalization API
from .v1.router import router as v1_router  # noqa: E402
app.include_router(v1_router, prefix="/v1")
