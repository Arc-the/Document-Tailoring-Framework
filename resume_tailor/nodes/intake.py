"""Intake node — validation, normalization, and resume parsing.

No LLM call needed. This is purely deterministic.
"""

from resume_tailor.parsers.resume_parser import parse_resume
from resume_tailor.state import ResumeState
from resume_tailor.utils.validation import clean_input_text


def intake_node(state: ResumeState) -> dict:
    """Validate inputs, clean text, and parse the resume into structured form."""
    # Validate required fields
    job_description = state.get("job_description", "")
    baseline_resume = state.get("baseline_resume", "")

    if not job_description.strip():
        raise ValueError("job_description is required and cannot be empty")
    if not baseline_resume.strip():
        raise ValueError("baseline_resume is required and cannot be empty")

    # Clean raw input text (copy-paste artifacts, unicode, excessive whitespace)
    job_description = clean_input_text(job_description)
    baseline_resume = clean_input_text(baseline_resume)

    # Parse resume into structured form
    parsed = parse_resume(baseline_resume)

    # Set defaults
    constraints = state.get("constraints") or {}
    company_name = state.get("company_name", "")
    target_role = state.get("target_role", "")

    return {
        "job_description": job_description,
        "baseline_resume": baseline_resume,
        "parsed_resume": parsed,
        "company_name": company_name.strip(),
        "target_role": target_role.strip(),
        "constraints": constraints,
        "research_context": {},
        "iteration_count": 0,
    }
