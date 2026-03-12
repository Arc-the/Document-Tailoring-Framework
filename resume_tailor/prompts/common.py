"""Shared prompt fragments used across multiple nodes."""

BASELINE_TRUTH_RULE = """CRITICAL CONSTRAINT — Baseline Truth:
- Every factual claim in the output must trace back to the baseline resume.
- You MUST NOT invent metrics, percentages, dollar amounts, team sizes, or outcomes.
- If the original says "improved performance", you cannot say "improved performance by 40%".
- If the original says "managed a team", you cannot say "managed a team of 12 engineers".
- You may rephrase for clarity and impact, but the underlying facts must be preserved exactly."""

FORMATTING_RULES = """Resume Formatting Rules:
- Use consistent bullet markers (prefer "- " or "• ")
- Each bullet should be 1-2 lines max
- Start every bullet with a strong action verb in past tense (unless it's a current role)
- Avoid first-person pronouns (I, my, we)
- Use quantitative evidence where the original resume provides it — but never fabricate numbers"""

TONE_GUIDANCE = """Tone:
- Professional and confident, not boastful
- Specific and concrete, not vague
- Achievement-oriented, not duty-oriented ("Reduced deployment time by 30%" not "Responsible for deployments")"""
