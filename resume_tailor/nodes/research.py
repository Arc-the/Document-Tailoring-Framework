"""Research node — optional web search for company context.

This is the least reliable node. The pipeline must produce strong results
even if this node returns nothing.
"""

import os
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from resume_tailor.config import get_config
from resume_tailor.state import ResumeState

logger = logging.getLogger(__name__)

RESEARCH_SYSTEM = """You are a research assistant helping tailor a resume. You've been given search results about a company and role.

Categorize each piece of information into exactly one bucket:
- resume_relevant: Directly useful for tailoring the resume (company products, tech stack, team structure, recent achievements)
- supplementary: Useful for wording or summary framing (company mission, values, culture keywords)
- interview_only: Interesting but not for the resume (interview process, salary range, office locations)
- discard: Not useful

Output a JSON object with these four keys, each containing a list of strings (the relevant facts)."""

RESEARCH_USER = """Company: {company_name}
Target Role: {target_role}
Job Description Summary: {jd_summary}

Search Results:
{search_results}

Categorize these findings into the four buckets."""


def research_node(state: ResumeState) -> dict:
    """Perform optional web research about the company and role.

    Returns empty research_context if research is disabled or fails.
    """
    config = get_config()

    if not config.enable_research:
        logger.info("Research disabled, skipping")
        return {"research_context": {}}

    company_name = state.get("company_name", "")
    target_role = state.get("target_role", "")

    if not company_name:
        logger.info("No company name provided, skipping research")
        return {"research_context": {}}

    # Try to use Tavily for search
    tavily_key = os.environ.get("TAVILY_API_KEY")
    if not tavily_key:
        logger.warning("TAVILY_API_KEY not set, skipping research")
        return {"research_context": {}}

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=tavily_key)

        queries = [
            f"{company_name} {target_role} engineering team",
            f"{company_name} technology stack products",
            f"{company_name} recent news achievements 2024 2025",
        ]

        all_results = []
        for query in queries:
            try:
                response = client.search(
                    query=query,
                    max_results=config.max_search_results,
                )
                for result in response.get("results", []):
                    all_results.append(
                        f"[{result.get('title', 'N/A')}] {result.get('content', '')}"
                    )
            except Exception as e:
                logger.warning(f"Search query failed: {query}, error: {e}")

        if not all_results:
            return {"research_context": {}}

        # Use LLM to categorize results
        jd_summary = state["job_description"][:500]
        search_text = "\n\n".join(all_results[:15])  # limit to avoid token overflow

        llm = config.get_llm(temperature=0.1)

        response = llm.invoke([
            SystemMessage(content=RESEARCH_SYSTEM),
            HumanMessage(content=RESEARCH_USER.format(
                company_name=company_name,
                target_role=target_role,
                jd_summary=jd_summary,
                search_results=search_text,
            )),
        ])

        # Parse the response — expect JSON
        import json
        try:
            context = json.loads(response.content)
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            content = response.content
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                context = json.loads(content[start:end])
            else:
                logger.warning("Could not parse research response as JSON")
                context = {}

        return {"research_context": context}

    except ImportError:
        logger.warning("tavily package not installed. Install with: pip install tavily-python")
        return {"research_context": {}}
    except Exception as e:
        logger.error(f"Research node failed: {e}")
        return {"research_context": {}}
