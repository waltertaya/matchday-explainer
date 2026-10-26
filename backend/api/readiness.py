"""Cheap, read-only demo checks. Never send a paid AI request here."""
from sqlalchemy import text

from api import db
from rag import config
from streaming import state as mstate


def readiness():
    checks = {}
    try:
        mstate.r().ping()
        checks["redis"] = {"status": "ready", "detail": "Live state is reachable"}
    except Exception:
        checks["redis"] = {"status": "unavailable", "detail": "Live updates need Redis; saved matches still work"}
    try:
        count = db.session.execute(text("SELECT COUNT(*) FROM document_chunks")).scalar_one()
        checks["laws"] = {
            "status": "ready" if count else "empty", "chunks": count,
            "detail": f"{count} indexed IFAB passages" if count else "Index the IFAB documents before the demo",
        }
    except Exception:
        db.session.rollback()
        checks["laws"] = {"status": "unavailable", "detail": "IFAB retrieval needs the configured PostgreSQL index"}
    checks["ai"] = {
        "status": "configured" if config.OPENAI_API_KEY else "missing",
        "detail": "Credentials configured; model access is not tested" if config.OPENAI_API_KEY else "Source-data summaries remain available without an AI key",
    }
    ready = (checks["redis"]["status"] == "ready" and checks["laws"]["status"] == "ready"
             and checks["ai"]["status"] == "configured")
    return {"status": "ready" if ready else "degraded", "checks": checks,
            "note": "Local checks only. Azure consumer connectivity and AI billing/model access are not probed."}
