"""
backend/app/api/v1/endpoints/activity.py
GET  /activity/         Recent activity feed
GET  /activity/stream   Serverless-safe polling endpoint (replaces SSE)

NOTE: True SSE (infinite streaming) is incompatible with Vercel serverless
functions because they terminate after the response is sent. This endpoint
returns the latest N activity items as plain JSON so the frontend can poll
it on a short interval (e.g. every 5 seconds) instead.
"""
from fastapi import APIRouter, Query
from app.services.mongo_service import get_activity_feed

router = APIRouter()


def _serialize_activity(i) -> dict:
    return {
        "id": str(i.id),
        "type": i.type,
        "message": i.message,
        "color": i.color,
        "candidate_id": i.candidate_id,
        "job_id": i.job_id,
        "run_id": i.run_id,
        "created_at": i.created_at.isoformat(),
    }


@router.get("/")
async def activity_feed(limit: int = 30):
    """Return recent activity items (newest first)."""
    items = await get_activity_feed(limit=limit)
    return [_serialize_activity(i) for i in items]


@router.get("/stream")
async def activity_stream(limit: int = Query(default=10, le=50)):
    """
    Serverless-compatible activity polling endpoint.

    Previously this was a true SSE stream (infinite loop), which fails on
    Vercel because serverless functions cannot hold persistent connections.
    The frontend now polls this endpoint every few seconds instead.
    Returns the latest `limit` activity items as JSON.
    """
    items = await get_activity_feed(limit=limit)
    return [_serialize_activity(i) for i in items]
