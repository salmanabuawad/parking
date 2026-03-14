from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, cameras, sample, settings as settings_router, tickets, upload, ticket_screenshots

app = FastAPI(title="Parking Enforcement API")
app.include_router(auth.router, prefix="/api")
app.include_router(sample.router, prefix="/api")
app.include_router(cameras.router, prefix="/api")
app.include_router(tickets.router, prefix="/api")
app.include_router(ticket_screenshots.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5180",
        "http://127.0.0.1:5180",
        "http://localhost:5182",
        "http://127.0.0.1:5182",
    ],
    allow_origin_regex=r"http://127\.0\.0\.1:\d+|http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "ok", "message": "Parking Enforcement API"}

@app.get("/health")
def health():
    return {"status": "healthy"}
