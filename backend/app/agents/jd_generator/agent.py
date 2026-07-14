"""
backend/app/agents/jd_generator/agent.py
"""
import json
import re
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from app.core.config import settings
from app.models.schemas import JobRequirements, GeneratedJD
from app.agents.jd_generator.prompt import SYSTEM_PROMPT, JD_GENERATION_PROMPT


class JDGeneratorAgent:
    def __init__(self):
        self.llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.7, groq_api_key=settings.GROQ_API_KEY)

    def generate(self, requirements: JobRequirements) -> GeneratedJD:
        # Pre-substitute hr_email directly into the prompt string BEFORE
        # passing to LangChain, so the LLM receives the real email address
        # and never sees a placeholder it might echo literally.
        hr_email_value = requirements.hr_email or "recruitment@company.com"
        resolved_prompt = JD_GENERATION_PROMPT.replace("{hr_email}", hr_email_value)

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("user", resolved_prompt),
        ])

        # Build the invoke dict without hr_email (already substituted above)
        invoke_data = {
            "job_title": requirements.job_title,
            "company_name": requirements.company_name,
            "key_requirements": requirements.key_requirements,
            "location": requirements.location,
            "experience_years": requirements.experience_years,
            "salary_range": requirements.salary_range,
            "employment_type": requirements.employment_type,
        }

        result = (prompt | self.llm).invoke(invoke_data)
        text = result.content

        def extract(label):
            m = re.search(rf"{label}:\s*(.*?)(?=\n[A-Z_]+:|$)", text, re.DOTALL)
            return m.group(1).strip() if m else ""

        def extract_json(label):
            m = re.search(rf"{label}:\s*(\[.*?\])", text, re.DOTALL)
            try:
                return json.loads(m.group(1)) if m else []
            except Exception:
                return []

        return GeneratedJD(
            job_title=requirements.job_title,
            company_name=requirements.company_name,
            job_description=extract("FULL_JD") or text,
            short_description=extract("SHORT_LINKEDIN"),
            required_skills=extract_json("REQUIRED_SKILLS_JSON"),
            nice_to_have=extract_json("NICE_TO_HAVE_JSON"),
        )