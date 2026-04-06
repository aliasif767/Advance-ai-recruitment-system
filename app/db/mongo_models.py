"""
backend/app/db/mongo_models.py
MongoDB document models using Beanie ODM.
Collections: jobs, candidates, applications, pipeline_runs, activity_feed
"""
from datetime import datetime
from typing import Optional, List, Any, Dict
from beanie import Document, Indexed
from pydantic import Field


# ─── Job Collection ───────────────────────────────────────────────────────────

class JobDocument(Document):
    title: str
    company: str
    description: str
    short_description: str = ""
    requirements: str
    location: str = "Remote"
    employment_type: str = "Full-time"
    experience_years: int = 0
    salary_range: str = ""
    required_skills: List[str] = Field(default_factory=list)
    nice_to_have: List[str] = Field(default_factory=list)
    status: str = "draft"          # draft | posted | closed
    linkedin_posted: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "jobs"


# ─── Candidate Collection ─────────────────────────────────────────────────────

class EvaluationScore(Document):
    category: str = ""
    score: int = 0
    notes: str = ""

    class Settings:
        name = "evaluation_scores"


class CandidateDocument(Document):
    # Identity
    name: str = "Unknown"
    email: str = ""
    phone: str = ""
    university: str = ""
    cgpa: str = ""
    github_handle: str = ""
    years_of_experience: str = "Unknown"
    cv_filename: str = ""
    cv_path: str = ""

    # Scoring
    match_score: int = 0
    final_decision: str = "NO_MATCH"   # MATCH | MAYBE | NO_MATCH

    # Job reference
    job_id: Optional[str] = None
    job_title: str = ""

    # Analysis
    skill_matches: List[Dict[str, Any]] = Field(default_factory=list)
    language_matches: List[Dict[str, Any]] = Field(default_factory=list)
    project_highlights: List[Dict[str, Any]] = Field(default_factory=list)
    evaluation_scores: List[Dict[str, Any]] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)
    cultural_fit_notes: str = ""
    github_summary: str = ""

    # Communication
    outreach_email_draft: str = ""
    rejection_email_draft: str = ""
    email_sent: bool = False
    email_sent_at: Optional[datetime] = None

    # Interview
    interview_scheduled: bool = False
    interview_slot: Optional[str] = None

    # Meta
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "candidates"


# ─── Pipeline Run Collection ──────────────────────────────────────────────────

class PipelineRunDocument(Document):
    run_id: str
    job_id: Optional[str] = None
    job_title: str = ""
    company: str = ""
    status: str = "running"          # running | completed | failed
    total_cvs: int = 0
    matched: int = 0
    maybe: int = 0
    no_match: int = 0
    emails_sent: int = 0
    errors: List[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    class Settings:
        name = "pipeline_runs"


# ─── Activity Feed Collection ─────────────────────────────────────────────────

class ActivityDocument(Document):
    type: str                        # score | email | github | jd | post | ingest
    message: str
    color: str = "#5B9CF6"
    candidate_id: Optional[str] = None
    job_id: Optional[str] = None
    run_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "activity_feed"


# ─── Stats Collection (cached aggregates) ────────────────────────────────────

class StatsDocument(Document):
    key: str                         # e.g. "global" or "job_<id>"
    total_cvs: int = 0
    total_matched: int = 0
    total_maybe: int = 0
    total_no_match: int = 0
    total_emails_sent: int = 0
    total_interviews: int = 0
    total_jobs: int = 0
    weekly_cvs: List[int] = Field(default_factory=lambda: [0]*7)
    weekly_matches: List[int] = Field(default_factory=lambda: [0]*7)
    score_distribution: List[int] = Field(default_factory=lambda: [0]*6)
    skill_coverage: Dict[str, int] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "stats"
