"""
backend/app/api/v1/endpoints/activity.py
GET  /activity/         Recent activity feed
GET  /activity/stream   SSE stream for real-time frontend updates
"""
import asyncio
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.services.mongo_service import get_activity_feed

router = APIRouter()


@router.get("/")
async def activity_feed(limit: int = 30):
    items = await get_activity_feed(limit=limit)
    return [
        {
            "id": str(i.id),
            "type": i.type,
            "message": i.message,
            "color": i.color,
            "candidate_id": i.candidate_id,
            "job_id": i.job_id,
            "run_id": i.run_id,
            "created_at": i.created_at.isoformat(),
        }
        for i in items
    ]


@router.get("/stream")
async def activity_stream():
    """Server-Sent Events stream — frontend listens for live updates."""
    async def event_generator():
        seen_ids = set()
        while True:
            items = await get_activity_feed(limit=10)
            for item in reversed(items):
                item_id = str(item.id)
                if item_id not in seen_ids:
                    seen_ids.add(item_id)
                    data = json.dumps({
                        "id": item_id,
                        "type": item.type,
                        "message": item.message,
                        "color": item.color,
                        "created_at": item.created_at.isoformat(),
                    })
                    yield f"data: {data}\n\n"
            await asyncio.sleep(3)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
