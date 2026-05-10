from __future__ import annotations

from pathlib import Path
from time import perf_counter

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError

from admin_backend.auth import get_current_username, public_router, require_api_group, require_main_api_access
from admin_backend.api import router
from admin_backend.routers.qteasy import router as qteasy_router
from admin_backend.routers.rbac import router as rbac_router
from app.models.migrations import ensure_schema
from app.utils.init_data import ensure_seed_data
from app.utils.logger import get_logger
from app.utils.runtime_home import get_install_root
from app.utils.task_runtime import ensure_runtime_states

app = FastAPI(title="bili admin backend", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)
logger = get_logger("admin_backend")
SLOW_REQUEST_THRESHOLD_SECONDS = 2.0

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public_router, prefix="/api")
app.include_router(public_router)
app.include_router(router, prefix="/api", dependencies=[Depends(require_main_api_access)])
app.include_router(qteasy_router, prefix="/api", dependencies=[Depends(require_api_group("api.qteasy"))])
app.include_router(rbac_router, prefix="/api", dependencies=[Depends(require_api_group("api.auth_admin"))])


@app.middleware("http")
async def log_slow_requests(request: Request, call_next):
    started = perf_counter()
    try:
        response = await call_next(request)
    finally:
        elapsed = perf_counter() - started
        if elapsed >= SLOW_REQUEST_THRESHOLD_SECONDS:
            logger.warning(
                "slow request method=%s path=%s query=%s duration_ms=%d",
                request.method,
                request.url.path,
                request.url.query or "-",
                int(elapsed * 1000),
            )
    return response


@app.exception_handler(OperationalError)
async def handle_operational_error(request: Request, exc: OperationalError):
    message = str(exc).lower()
    if "database is locked" in message or "database schema is locked" in message:
        logger.warning(
            "database busy method=%s path=%s detail=%s",
            request.method,
            request.url.path,
            str(exc),
        )
        return JSONResponse(
            status_code=503,
            content={
                "detail": "SQLite is busy. Retry the request shortly.",
                "code": "sqlite_busy",
            },
        )

    logger.error(
        "database error method=%s path=%s detail=%s",
        request.method,
        request.url.path,
        str(exc),
    )
    return JSONResponse(status_code=500, content={"detail": "Database operation failed"})


@app.get("/openapi.json", include_in_schema=False)
def protected_openapi(_: str = Depends(get_current_username)):
    return app.openapi()


@app.get("/docs", include_in_schema=False)
def protected_docs(_: str = Depends(get_current_username)):
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="bili admin backend - Swagger UI",
        oauth2_redirect_url="/docs/oauth2-redirect",
    )


@app.get("/docs/oauth2-redirect", include_in_schema=False)
def protected_docs_redirect(_: str = Depends(get_current_username)):
    return get_swagger_ui_oauth2_redirect_html()


@app.get("/redoc", include_in_schema=False)
def protected_redoc(_: str = Depends(get_current_username)):
    return get_redoc_html(openapi_url="/openapi.json", title="bili admin backend - ReDoc")


_dist_dir = get_install_root() / "web" / "dist"
if _dist_dir.exists():
    app.mount("/", StaticFiles(directory=_dist_dir, html=True), name="web")


@app.on_event("startup")
def on_startup() -> None:
    startup_started = perf_counter()
    logger.info("startup begin")

    step_started = perf_counter()
    ensure_schema()
    logger.info("startup step=ensure_schema duration_ms=%d", int((perf_counter() - step_started) * 1000))

    step_started = perf_counter()
    ensure_runtime_states()
    logger.info("startup step=ensure_runtime_states duration_ms=%d", int((perf_counter() - step_started) * 1000))

    step_started = perf_counter()
    ensure_seed_data()
    logger.info("startup step=ensure_seed_data duration_ms=%d", int((perf_counter() - step_started) * 1000))

    logger.info("startup finished duration_ms=%d", int((perf_counter() - startup_started) * 1000))


@app.get("/")
def root():
    if _dist_dir.exists():
        return JSONResponse({"message": "frontend is served from /"})
    return {
        "message": "Bili admin backend is running",
        "frontend": "run web/ separately with npm install && npm run dev",
    }


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "ok"}
