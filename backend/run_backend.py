"""Run uvicorn with log_config=None to avoid dictConfig issues on Python 3.13."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_config=None,  # use default Python logging; avoids dictConfig crash
    )
