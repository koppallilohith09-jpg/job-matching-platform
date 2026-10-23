"""Local application plumbing. Each project contains its own copy."""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, root):
        self.directory = Path(os.environ.get("APP_DATA_DIR", Path(root) / "data"))
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "workspace.sqlite3"
        with self.transaction() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY, created TEXT NOT NULL,
                    action TEXT NOT NULL, details TEXT NOT NULL);
            """)

    @contextmanager
    def transaction(self):
        connection = sqlite3.connect(self.path, timeout=20)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def get(self, key, fallback=None):
        with self.transaction() as db:
            row = db.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else fallback

    def put(self, key, value):
        with self.transaction() as db:
            db.execute("INSERT INTO state VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       (key, json.dumps(value, allow_nan=False)))

    def audit(self, action, details):
        with self.transaction() as db:
            db.execute("INSERT INTO audit(created,action,details) VALUES (?,?,?)",
                       (now(), action, json.dumps(details)))

    def history(self, limit=100):
        with self.transaction() as db:
            return [dict(row) for row in db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,))]


def create_app(root, title):
    root = Path(root)
    app = FastAPI(title=title, docs_url=None, redoc_url=None)

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        host = request.url.hostname
        if host not in {"127.0.0.1", "localhost", "testserver"}:
            return JSONResponse({"detail": "Localhost requests only"}, status_code=403)
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse({"detail": "Origin rejected"}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Cross-site request rejected"}, status_code=403)
        if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get("x-workspace") != "1":
            return JSONResponse({"detail": "Request header required"}, status_code=403)
        try:
            if int(request.headers.get("content-length", 0)) > 8_000_000:
                return JSONResponse({"detail": "Request exceeds 8 MB"}, status_code=413)
        except ValueError:
            return JSONResponse({"detail": "Invalid request size"}, status_code=400)
        response = await call_next(request)
        response.headers.update({
            "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
            "Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
                "base-uri 'none'; frame-ancestors 'none'",
        })
        return response

    @app.exception_handler(ValueError)
    async def bad_value(request, error):
        return JSONResponse({"detail": str(error)}, status_code=400)

    @app.get("/")
    def index():
        return FileResponse(root / "static" / "index.html")

    app.mount("/static", StaticFiles(directory=root / "static"), name="static")
    return app
