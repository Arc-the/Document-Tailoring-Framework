"""Shared prompt fragments — generic defaults that plugins can override."""

BASELINE_TRUTH_RULE = """CRITICAL CONSTRAINT — Baseline Truth:
- Every factual claim in the output must trace back to the source document.
- You MUST NOT invent metrics, percentages, dollar amounts, team sizes, or outcomes.
- You may rephrase for clarity and impact, but the underlying facts must be preserved exactly."""

FORMATTING_RULES = """Formatting Rules:
- Use consistent bullet markers (prefer "- " or "• ")
- Each bullet should be 1-2 lines max
- Start every bullet with a strong action verb
- Use quantitative evidence where the original provides it — but never fabricate numbers"""

TONE_GUIDANCE = """Tone:
- Professional and confident, not boastful
- Specific and concrete, not vague
- Achievement-oriented, not duty-oriented"""
