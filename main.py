#!/usr/bin/env python3
import os
import uvicorn

PORT = int(os.environ.get("PORT", 8000))
HOST = "0.0.0.0"

if __name__ == "__main__":
    print(f"Starting Sports Bot on {HOST}:{PORT}")
    uvicorn.run(
        "api.webhook:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info"
    )
