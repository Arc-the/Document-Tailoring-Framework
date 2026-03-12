"""CLI entry point for the resume tailoring pipeline."""

import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from resume_tailor.graph import build_graph
from resume_tailor.config import PipelineConfig, set_config
from resume_tailor.parsers.file_reader import read_file


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Tailor a resume to a specific job description"
    )
    parser.add_argument(
        "--resume", "-r",
        required=True,
        help="Path to baseline resume (.txt, .pdf, or .docx)",
    )
    parser.add_argument(
        "--job", "-j",
        required=True,
        help="Path to job description (.txt, .pdf, or .docx)",
    )
    parser.add_argument(
        "--company", "-c",
        default="",
        help="Company name (for research)",
    )
    parser.add_argument(
        "--role",
        default="",
        help="Target role title",
    )
    parser.add_argument(
        "--output", "-o",
        default="output/tailored_resume.txt",
        help="Output file path (default: output/tailored_resume.txt)",
    )
    parser.add_argument(
        "--constraints",
        default=None,
        help='JSON string of constraints, e.g. \'{"max_pages": 1, "tone": "technical"}\'',
    )
    parser.add_argument(
        "--provider", "-p",
        default="openai",
        choices=["openai", "gemini"],
        help="LLM provider (default: openai)",
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="Model name override (default: gpt-4o for openai, gemini-2.0-flash for gemini)",
    )
    parser.add_argument(
        "--max-experiences",
        type=int,
        default=4,
        help="Max experience blocks to keep (default: 4, 0 = no limit)",
    )
    parser.add_argument(
        "--research",
        action="store_true",
        help="Enable web research about the company",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)
    logger = logging.getLogger("main")

    # Read input files
    resume_path = Path(args.resume)
    job_path = Path(args.job)

    if not resume_path.exists():
        logger.error(f"Resume file not found: {resume_path}")
        sys.exit(1)
    if not job_path.exists():
        logger.error(f"Job description file not found: {job_path}")
        sys.exit(1)

    try:
        baseline_resume = read_file(resume_path)
        job_description = read_file(job_path)
    except (ValueError, ImportError) as e:
        logger.error(str(e))
        sys.exit(1)

    # Parse constraints
    constraints = {}
    if args.constraints:
        try:
            constraints = json.loads(args.constraints)
        except json.JSONDecodeError:
            logger.error("Invalid JSON in --constraints")
            sys.exit(1)

    # Configure pipeline
    provider = args.provider
    if args.model:
        model_name = args.model
    elif provider == "gemini":
        model_name = "gemini-2.5-flash"
    else:
        model_name = "gpt-4o"

    config = PipelineConfig(
        provider=provider,
        model_name=model_name,
        enable_research=args.research,
        max_experiences=args.max_experiences,
    )
    set_config(config)
    logger.info(f"Using {provider} / {model_name}")

    # Build and run the graph
    logger.info("Building pipeline...")
    app = build_graph()

    initial_state = {
        "job_description": job_description,
        "baseline_resume": baseline_resume,
        "company_name": args.company,
        "target_role": args.role,
        "constraints": constraints,
    }

    logger.info("Running pipeline...")
    result = app.invoke(initial_state)

    # Output results
    tailored_resume = result.get("tailored_resume", "")
    evaluation = result.get("evaluation")

    if not tailored_resume:
        logger.error("Pipeline produced no output")
        sys.exit(1)

    # Write output
    output_path = Path(args.output)
    output_path.write_text(tailored_resume, encoding="utf-8")
    logger.info(f"Tailored resume written to: {output_path}")

    # Print evaluation summary
    if evaluation:
        print("\n=== Evaluation Summary ===")
        print(f"Passed: {evaluation.passed}")
        print(f"Iterations: {result.get('iteration_count', 0)}")
        print("Scores:")
        for dim, score in evaluation.scores.items():
            status = "✓" if score >= 7.0 else "✗"
            print(f"  {status} {dim}: {score:.1f}")
        if evaluation.critique:
            print(f"\nFeedback: {evaluation.critique}")

    print(f"\nResume saved to: {output_path}")


if __name__ == "__main__":
    main()
