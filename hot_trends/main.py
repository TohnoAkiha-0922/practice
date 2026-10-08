"""
AI Hot Trends - Real-time trending dashboard for B站/抖音/微博
Run: python main.py  or  uvicorn main:app --reload
"""

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import webbrowser
import threading
import uvicorn

from crawler import fetch_all

app = FastAPI(title="AI Hot Trends", version="1.0.0")


@app.get("/api/trends")
async def get_trends(ai_only: bool = Query(False, description="Only return AI-related items")):
    """Fetch trends from all platforms, optionally filtered by AI keywords."""
    data = await fetch_all()
    if ai_only:
        filtered = {}
        for platform, items in data.items():
            filtered[platform] = [item for item in items if item.get("ai")]
        return filtered
    return data


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "templates" / "index.html"
    return html_path.read_text(encoding="utf-8")


def open_browser():
    webbrowser.open("http://127.0.0.1:8000")


if __name__ == "__main__":
    threading.Timer(1.5, open_browser).start()
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False, log_level="info")
