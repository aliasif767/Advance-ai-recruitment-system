"""
backend/app/api/v1/endpoints/stats.py
GET /stats/global   Dashboard KPIs, charts, funnel data
"""
from fastapi import APIRouter
from app.services.mongo_service import get_global_stats

router = APIRouter()


@router.get("/global")
async def global_stats():
    return await get_global_stats()
