"""
backend/app/db/interview_models.py
Beanie ODM document models for the AI Smart Interview & Assessment Module.
Collections: assessments, questions, assessment_sessions, violation_logs, evaluation_reports
"""
from datetime import datetime
from typing import Optional, List, Any, Dict
from beanie import Document
from pydantic import Field


# ─── Assessment Collection ────────────────────────────────────────────────────

class AssessmentConfig(Document):
    """Embedded config for an assessment (not a top-level collection)."""
    duration_minutes: int = 60
    total_questions: int = 30
    easy_count: int = 10
    medium_count: int = 15
    hard_count: int = 5
    adaptive: bool = True
    proctoring_enabled: bool = True
    camera_enabled: bool = False
    question_types: Dict[str, int] = Field(default_factory=lambda: {
        "mcq": 15, "coding": 5, "short_answer": 7, "case_study": 3
    })

    class Settings:
        name = "assessment_configs"


class AssessmentDocument(Document):
    """One assessment per candidate+job pair."""
    candidate_id: str
    job_id: str
    candidate_name: str = ""
    candidate_email: str = ""
    job_title: str = ""
    company: str = ""

    # Security
    token: str                              # UUID token for portal URL
    assessment_url: str = ""

    # State
    status: str = "pending"                 # pending | active | submitted | evaluated | expired

    # Questions
    question_ids: List[str] = Field(default_factory=list)

    # Config
    duration_minutes: int = 60
    total_questions: int = 30
    easy_count: int = 10
    medium_count: int = 15
    hard_count: int = 5
    adaptive: bool = True
    proctoring_enabled: bool = True
    camera_enabled: bool = False
    question_types: Dict[str, int] = Field(default_factory=lambda: {
        "mcq": 15, "coding": 5, "short_answer": 7, "case_study": 3
    })

    # Scores (populated after evaluation)
    resume_score: int = 0
    mcq_score: float = 0.0
    coding_score: float = 0.0
    short_answer_score: float = 0.0
    communication_score: float = 0.0
    problem_solving_score: float = 0.0
    cheating_penalty: int = 0
    final_composite_score: float = 0.0

    # Timestamps
    scheduled_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    evaluated_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "assessments"


# ─── Question Bank Collection ─────────────────────────────────────────────────

class TestCase(Document):
    """Embedded test case for coding questions."""
    input: str = ""
    expected_output: str = ""
    hidden: bool = False
    description: str = ""

    class Settings:
        name = "test_cases"


class QuestionDocument(Document):
    """Reusable question bank entry."""
    # Classification
    job_id: Optional[str] = None            # None = global/reusable
    skill: str = ""
    technology: str = ""
    topic: str = ""
    type: str = "mcq"                       # mcq | true_false | fill_blank | short_answer | long_answer | coding | case_study | sql | system_design | debugging | output_prediction
    difficulty: str = "medium"              # easy | medium | hard
    experience_level: str = "mid"           # junior | mid | senior

    # Content
    question_text: str = ""
    options: List[Dict[str, str]] = Field(default_factory=list)  # [{"id": "a", "text": "..."}]
    correct_answers: List[str] = Field(default_factory=list)     # ["a"] or ["a", "c"] for multi
    explanation: str = ""

    # Coding-specific
    code_template: str = ""                 # Starter code for candidate
    language: str = "python"               # python | javascript | java | cpp | go
    test_cases: List[Dict[str, Any]] = Field(default_factory=list)
    time_limit_seconds: int = 60
    memory_limit_mb: int = 256

    # Fill-in-blank
    blank_answer: str = ""

    # Tags & meta
    tags: List[str] = Field(default_factory=list)
    source: str = "ai_generated"            # ai_generated | uploaded | manual

    # Analytics (updated after each use)
    times_used: int = 0
    times_correct: int = 0
    pass_rate: float = 0.0
    avg_time_seconds: float = 0.0
    too_easy: bool = False
    too_hard: bool = False

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "questions"


# ─── Assessment Session Collection ───────────────────────────────────────────

class SessionAnswer(Document):
    """Embedded answer within a session."""
    question_id: str = ""
    question_type: str = ""
    answer: Any = None                      # str | List[str] | dict (for coding)
    time_taken_seconds: int = 0
    skipped: bool = False
    answered_at: Optional[datetime] = None

    class Settings:
        name = "session_answers"


class AssessmentSessionDocument(Document):
    """Live session state for an in-progress assessment."""
    assessment_id: str
    candidate_id: str

    # State
    status: str = "lobby"                   # lobby | active | paused | submitted | timed_out
    current_question_idx: int = 0

    # Adaptive tracking
    current_difficulty: str = "easy"
    correct_streak: int = 0
    wrong_streak: int = 0
    correct_count: int = 0
    total_answered: int = 0

    # Timer
    time_remaining_seconds: int = 3600
    total_duration_seconds: int = 3600

    # Answers (stored as list of dicts for flexibility)
    answers: List[Dict[str, Any]] = Field(default_factory=list)

    # Proctoring
    tab_switches: int = 0
    window_blurs: int = 0
    copy_attempts: int = 0
    paste_attempts: int = 0
    right_clicks: int = 0
    devtools_detected: int = 0
    face_not_detected: int = 0
    multiple_faces: int = 0
    phone_detected: int = 0
    screenshot_count: int = 0
    total_violations: int = 0

    # Timestamps
    started_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "assessment_sessions"


# ─── Violation Log Collection ─────────────────────────────────────────────────

class ViolationLogDocument(Document):
    """Detailed proctoring violation log entry."""
    session_id: str
    assessment_id: str
    candidate_id: str

    violation_type: str                     # tab_switch | window_blur | copy | paste | right_click | devtools | face_not_detected | multiple_faces | phone_detected | suspicious_behavior
    severity: str = "low"                   # low | medium | high | critical
    description: str = ""
    screenshot_b64: Optional[str] = None    # Base64 encoded screenshot (optional)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    logged_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "violation_logs"


# ─── Evaluation Report Collection ─────────────────────────────────────────────

class ScoreBreakdown(Document):
    category: str = ""
    raw_score: float = 0.0
    weighted_score: float = 0.0
    weight_pct: int = 0
    notes: str = ""

    class Settings:
        name = "score_breakdowns"


class EvaluationReportDocument(Document):
    """Final AI-generated evaluation report per candidate."""
    candidate_id: str
    job_id: str
    assessment_id: str

    # Score components
    resume_score: int = 0
    mcq_score: float = 0.0
    coding_score: float = 0.0
    short_answer_score: float = 0.0
    communication_score: float = 0.0
    problem_solving_score: float = 0.0
    experience_score: float = 0.0
    education_score: float = 0.0
    behavior_score: float = 0.0
    cheating_penalty: int = 0

    # Final
    final_composite_score: float = 0.0
    score_breakdown: List[Dict[str, Any]] = Field(default_factory=list)

    # AI narrative
    candidate_summary: str = ""
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    technical_analysis: str = ""
    soft_skills_analysis: str = ""
    coding_performance: str = ""
    communication_assessment: str = ""
    recommendation: str = "reject"          # strongly_hire | hire | maybe | reject
    hiring_confidence: int = 0              # 0-100
    risk_analysis: str = ""
    overall_rating: float = 0.0            # 0-5.0

    # Anti-cheat summary
    cheating_summary: str = ""
    violation_count: int = 0

    generated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "evaluation_reports"


# ─── Question Upload Batch Collection ─────────────────────────────────────────

class QuestionUploadDocument(Document):
    """Tracks bulk question uploads from company files."""
    job_id: Optional[str] = None
    filename: str = ""
    file_format: str = ""                   # pdf | docx | xlsx | csv
    questions_extracted: int = 0
    questions_saved: int = 0
    status: str = "processing"             # processing | completed | failed
    error: str = ""
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "question_uploads"
