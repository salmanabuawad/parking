from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, cameras, sample, settings as settings_router, tickets, upload, ticket_screenshots, violation_rules as violation_rules_router, parking_zones as parking_zones_router, anpr as anpr_router
from app.routers import field_configurations as field_configurations_router
from app.routers import inspectors as inspectors_router, camera_segments as camera_segments_router
from app.routers import exemptions as exemptions_router
from app.routers import simulation as simulation_router
from app.routers import map_config as map_config_router

app = FastAPI(title="Parking Enforcement API")
app.include_router(auth.router, prefix="/api")
app.include_router(sample.router, prefix="/api")
app.include_router(cameras.router, prefix="/api")
app.include_router(tickets.router, prefix="/api")
app.include_router(ticket_screenshots.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")
app.include_router(violation_rules_router.router, prefix="/api")
app.include_router(parking_zones_router.router, prefix="/api")
app.include_router(field_configurations_router.router, prefix="/api")
app.include_router(anpr_router.router, prefix="/api")
app.include_router(inspectors_router.router, prefix="/api")
app.include_router(camera_segments_router.router, prefix="/api")
app.include_router(exemptions_router.router, prefix="/api")
app.include_router(simulation_router.router, prefix="/api")
app.include_router(map_config_router.router, prefix="/api")

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
        "http://185.229.226.37",
        "https://185.229.226.37",
        "https://parking.kortexd.com",
        "http://parking.kortexd.com",
    ],
    allow_origin_regex=r"http://127\.0\.0\.1:\d+|http://localhost:\d+|https?://185\.229\.226\.37(:\d+)?|https?://parking\.kortexd\.com",
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
