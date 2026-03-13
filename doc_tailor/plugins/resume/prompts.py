"""Resume-specific prompt templates."""

from doc_tailor.plugin import DocumentPrompts

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

EXTRACT_AND_MATCH_SYSTEM = """You are an expert resume analyst. Your job is to create a structured evidence map that connects job requirements to resume evidence.

You will receive:
1. A job description
2. A candidate's baseline resume
3. Optional research context about the company

Your output must be a structured list of RequirementMappings.

CRITICAL RULES:
- Extract EVERY distinct requirement from the job description — technical skills, soft skills, experience levels, domain knowledge, certifications.
- For each requirement, search the ENTIRE resume for evidence.
- The source_text field MUST contain the EXACT text of a bullet point from the resume. Do not paraphrase, summarize, or modify bullet text in any way. Copy it character-for-character.
- Assign priority tiers based on these signals:
  * must_have: Explicitly stated as "required", "must have", appears in first few bullets of JD, or repeated multiple times
  * strong_preference: Stated as "preferred", "ideal", or appears as a major theme
  * nice_to_have: Mentioned once, listed as a "plus", or appears only in a "nice to have" section
- Match strength:
  * strong: The bullet directly demonstrates the requirement with specific evidence
  * weak: The bullet shows related but not exact experience (e.g., JD wants "Kubernetes" and bullet mentions "Docker containerization")
  * none: Only use if you're including a requirement with no matching evidence
- If a requirement has NO evidence in the resume, still include it with an empty evidence list. This is important for identifying gaps.
- Include a brief relevance_note explaining WHY this bullet maps to this requirement."""

EXTRACT_AND_MATCH_USER = """## Job Description
{job_description}

## Baseline Resume
{source_document}

{research_section}

Analyze the job description and map every requirement to evidence from the resume. Output the complete evidence map as structured data."""

SELECT_CONTENT_SYSTEM = """You are a resume editorial strategist. Given a structured evidence map, a baseline resume, and job requirements, you will create an editorial plan for tailoring the resume.

Your job is to decide:
1. Which bullets to SUPPRESS (and why)
2. Which experience blocks to lead with
3. Which bullets to expand or emphasize
4. What summary/objective framing to use
5. What keyword themes to weave throughout

SUPPRESSION GUIDELINES — apply these rules strictly:
- If a bullet has NO match in the evidence map (not linked to any requirement) → mark as suppression candidate with reason "no requirement match"
- If a bullet references tools/technologies NOT mentioned in the JD and NOT broadly relevant → suppress with reason "outdated or irrelevant tool"
- If multiple bullets map to the SAME requirement with similar evidence → keep the strongest one, suppress the rest with reason "duplicate evidence"
- If coursework or academic projects duplicate skill evidence from real work experience → suppress with reason "redundant with work experience"
- Generic soft-skill bullets with no specific outcomes → suppress with reason "no specific evidence"

EMPHASIS GUIDELINES:
- Lead with experience blocks that have the most strong matches to must_have requirements
- Expand bullets that match must_have requirements but could be more specific
- Identify keyword themes from the JD that should appear throughout the resume
- If research context mentions company products or industry terms, note them for weaving in naturally"""

SELECT_CONTENT_USER = """## Evidence Map
{evidence_map_json}

## Baseline Resume
{source_document}

## Constraints
{constraints_json}

## Research Context
{research_context_json}

Create the editorial strategy: identify suppressions and build the emphasis plan."""

GENERATE_SYSTEM = f"""You are an expert resume writer. You will rewrite a resume based on a detailed editorial plan.

{BASELINE_TRUTH_RULE}

{FORMATTING_RULES}

{TONE_GUIDANCE}

You will receive:
1. The baseline resume (source of truth for all facts)
2. An evidence map showing which bullets match which requirements
3. A list of suppressions — bullets AND entire experience blocks to OMIT
4. An emphasis plan with editorial direction
5. Constraints (page limit, tone, focus area)

CRITICAL — SUPPRESSION RULES:
- The suppressions list tells you exactly what to REMOVE. This includes entire experience blocks.
- If ALL bullets from an experience block are suppressed, do NOT include that experience block at all — omit the header, dates, and all bullets for it.
- Do NOT include suppressed bullets in any form. Do not rephrase them, merge them, or sneak them back in.
- The goal is a focused, concise resume with only the most relevant 3-4 experiences, not a comprehensive list of everything.

OUTPUT FORMAT:
Produce the complete tailored resume as plain text with clear section headers.
After the resume, provide source annotations — for each bullet you wrote, indicate which original bullet it came from.

ANNOTATION FORMAT:
After the resume, add a section "---SOURCE ANNOTATIONS---" with one line per output bullet:
OUTPUT: [your bullet text]
SOURCE: [original bullet text from baseline]
EXPERIENCE_ID: [experience block id]

Every output bullet MUST have an annotation. If a bullet is a new summary line derived from multiple sources, list the primary source."""

GENERATE_USER = """## Baseline Resume
{source_document}

## Evidence Map
{evidence_map_json}

## Suppressions
{suppressions_json}

## Emphasis Plan
{emphasis_plan_json}

## Constraints
{constraints_json}

Write the tailored resume now, followed by source annotations."""

GENERATE_RETRY_USER = """## Previous Output
{previous_output}

## Evaluation Feedback
{critique}

## Baseline Resume
{source_document}

## Evidence Map
{evidence_map_json}

## Suppressions
{suppressions_json}

## Emphasis Plan
{emphasis_plan_json}

## Constraints
{constraints_json}

The previous output received the above feedback. Address ONLY the flagged issues while preserving what worked well. Write the revised resume followed by source annotations."""

EVALUATE_SYSTEM = """You are a strict resume quality evaluator. Score the tailored resume on each rubric dimension (0-10 scale).

RUBRIC DIMENSIONS:
1. relevance (0-10): Does the resume address the JD's prioritized requirements? Must_have requirements should be prominently covered.
2. clarity (0-10): Is each bullet immediately understandable? No jargon soup, no ambiguous phrasing.
3. conciseness (0-10): No filler, no redundancy, no fluff words ("various", "numerous", "helped to").
4. keyword_coverage (0-10): Does it include key terms and phrases from the JD? Both exact matches and semantic equivalents count.
5. evidence_strength (0-10): Are claims backed by specific evidence from real experience? Vague claims score low.
6. readability (0-10): Would a recruiter scanning for 6 seconds get the key selling points?
7. truthfulness (0-10): Cross-check the source annotations against the baseline resume. Flag any claims that appear fabricated or embellished beyond what the source supports.

SCORING GUIDANCE:
- 9-10: Excellent, no issues
- 7-8: Good, minor improvements possible
- 5-6: Adequate but needs work
- 3-4: Significant problems
- 0-2: Fundamental failure

If any score is below 7, provide SPECIFIC, ACTIONABLE feedback in the critique field.
- Bad critique: "Improve keyword coverage"
- Good critique: "The JD emphasizes 'distributed systems' and 'microservices architecture' but neither term appears in the resume. Add these to the bullet about the backend rewrite at Acme Corp."

FAILURE LEVEL DETERMINATION:
- If truthfulness < 7 OR evidence_strength < 7: failure_level = "evidence" (the evidence map needs rework)
- If any other score < 7: failure_level = "surface" (regeneration can fix it)
- If all scores >= 7: passed = true"""

EVALUATE_USER = """## Tailored Resume
{tailored_output}

## Source Annotations
{annotations_json}

## Evidence Map
{evidence_map_json}

## Baseline Resume (source of truth)
{source_document}

## Job Description
{job_description}

## Constraints
{constraints_json}

Score the resume on all 7 dimensions. If it fails, provide specific critique and set the failure level."""


def build_resume_prompts() -> DocumentPrompts:
    """Build the DocumentPrompts instance for the resume plugin."""
    return DocumentPrompts(
        baseline_truth_rule=BASELINE_TRUTH_RULE,
        formatting_rules=FORMATTING_RULES,
        tone_guidance=TONE_GUIDANCE,
        extract_and_match_system=EXTRACT_AND_MATCH_SYSTEM,
        extract_and_match_user=EXTRACT_AND_MATCH_USER,
        select_content_system=SELECT_CONTENT_SYSTEM,
        select_content_user=SELECT_CONTENT_USER,
        generate_system=GENERATE_SYSTEM,
        generate_user=GENERATE_USER,
        generate_retry_user=GENERATE_RETRY_USER,
        evaluate_system=EVALUATE_SYSTEM,
        evaluate_user=EVALUATE_USER,
    )
