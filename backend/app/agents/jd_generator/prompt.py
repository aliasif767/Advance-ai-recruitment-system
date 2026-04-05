SYSTEM_PROMPT = """You are a world-class technical recruiter and copywriter at a top tech company.
You write job descriptions that are detailed, compelling, and attract elite talent.
Your LinkedIn posts are professional, detailed, use emojis strategically, and always include
role details, responsibilities, required skills, what the company offers, and a clear call to action.
Never write a short one-liner. Always write a full, rich, detailed post of at least 400 characters."""

JD_GENERATION_PROMPT = """
Generate a FULL professional job description AND a detailed LinkedIn post.

Company: {company_name}
Role: {job_title}
Location: {location}
Employment Type: {employment_type}
Experience Required: {experience_years}+ years
Key Requirements: {key_requirements}
Salary Range: {salary_range}

Generate EXACTLY in this format:

FULL_JD:
## About the Role
Write 2-3 sentences describing the role and its strategic importance at {company_name}.

## Key Responsibilities
- Design and develop scalable solutions using the required tech stack
- Collaborate with cross-functional teams to deliver high-quality features
- Participate in code reviews and maintain high code quality standards
- Contribute to technical architecture decisions
- Mentor junior team members and share knowledge
- [Add 2 more specific responsibilities based on: {key_requirements}]

## Required Skills & Experience
- {experience_years}+ years of professional experience
- [List each skill from key requirements as a bullet point with detail]
- Strong problem-solving and communication skills
- Experience with agile/scrum development methodologies

## Nice to Have
- Experience with cloud platforms (AWS / GCP / Azure)
- Open source contributions
- Previous startup or product company experience

## What We Offer
- Competitive salary package {salary_range}
- Professional development budget and learning opportunities
- Flexible working hours and remote-friendly culture
- Collaborative and inclusive team environment
- Career growth with a fast-growing company

## How to Apply
Send your CV, GitHub profile, and a brief cover letter to our recruitment email.
Subject line: "Application for {job_title} - [Your Name]"

SHORT_LINKEDIN:
🚀 Exciting Career Opportunity: {job_title} at {company_name}! 🚀

{company_name} is growing and we're looking for a skilled {job_title} to join our dynamic team and help us build the future!

📍 Location: {location}
💼 Employment: {employment_type}
⏰ Experience: {experience_years}+ years required
💰 Salary: {salary_range}

🎯 About This Role:
As our new {job_title}, you will design and build scalable solutions, collaborate with talented engineers, and make a real impact on our products and millions of users.

🔧 Core Requirements:
• {key_requirements}
• Strong communication and teamwork skills
• Passion for clean code and best practices

🎁 Why Join {company_name}?
✔ Competitive compensation package
✔ Flexible & remote-friendly work environment
✔ Continuous learning & growth opportunities
✔ Work with a passionate, talented team
✔ Make a real difference in a fast-growing company

📩 How to Apply:
Send your CV and GitHub/portfolio link to our recruitment email with subject: "Application - {job_title}"

Don't miss this opportunity — apply today! 💪

#Hiring #NowHiring #{job_title} #TechJobs #SoftwareEngineering #{company_name} #CareerOpportunity #JobAlert

REQUIRED_SKILLS_JSON:
["skill1", "skill2", "skill3"]

NICE_TO_HAVE_JSON:
["skill1", "skill2", "skill3"]
"""