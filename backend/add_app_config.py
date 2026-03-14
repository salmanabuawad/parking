"""Add app_config table and seed default row."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import text
from app.database import engine
from app.models import AppConfig, Base

def main():
    Base.metadata.create_all(bind=engine)
    from sqlalchemy.orm import Session
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        cfg = db.query(AppConfig).first()
        if not cfg:
            cfg = AppConfig(id=1, blur_kernel_size=3, use_violation_pipeline=True)
            db.add(cfg)
            db.commit()
            print("Created default app_config")
        else:
            print("app_config already exists")
    finally:
        db.close()

if __name__ == "__main__":
    main()
