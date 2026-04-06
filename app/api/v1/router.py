from fastapi import APIRouter
from app.api.v1.endpoints import jobs, candidates, pipeline, stats, activity

api_router = APIRouter()
api_router.include_router(jobs.router,       prefix="/jobs",       tags=["Jobs"])
api_router.include_router(candidates.router, prefix="/candidates", tags=["Candidates"])
api_router.include_router(pipeline.router,   prefix="/pipeline",   tags=["Pipeline"])
api_router.include_router(stats.router,      prefix="/stats",      tags=["Stats"])
api_router.include_router(activity.router,   prefix="/activity",   tags=["Activity"])
