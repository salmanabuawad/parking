"""Run uvicorn with log_config=None to avoid dictConfig issues on Python 3.13."""
import os
import uvicorn

if __name__ == "__main__":
    production = os.environ.get("PRODUCTION", "").lower() in ("1", "true", "yes")
    uvicorn.run(
        "main:app",
        host="127.0.0.1" if production else "0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        reload=not production,
        log_config=None,  # use default Python logging; avoids dictConfig crash
    )
