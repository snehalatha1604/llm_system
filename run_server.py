#!/usr/bin/env python3
"""
Socket.IO enabled server launcher
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, log_level="warning")