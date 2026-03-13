"""CLI entry point for the document tailoring pipeline."""

import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from doc_tailor.graph import build_graph
from doc_tailor.config import PipelineConfig, set_config
from doc_tailor.parsers.file_reader import read_file
from doc_tailor.plugin import get_plugin


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
        description="Tailor a document to a specific target specification"
    )
    parser.add_argument(
        "--source", "--resume", "-r",
        required=True,
        dest="source",
        help="Path to source document (.txt, .pdf, or .docx)",
    )
    parser.add_argument(
        "--target", "--job", "-j",
        required=True,
        dest="target",
        help="Path to target specification (.txt, .pdf, or .docx)",
    )
    parser.add_argument(
        "--doc-type",
        default="resume",
        help="Document type plugin to use (default: resume)",
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
        default="output/tailored_output.txt",
        help="Output file path (default: output/tailored_output.txt)",
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
        help="Model name override (default: gpt-4o for openai, gemini-2.5-flash for gemini)",
    )
    parser.add_argument(
        "--max-experiences",
        type=int,
        default=None,
        help="Max experience blocks to keep (resume plugin, default: 4, 0 = no limit)",
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
    source_path = Path(args.source)
    target_path = Path(args.target)

    if not source_path.exists():
        logger.error(f"Source file not found: {source_path}")
        sys.exit(1)
    if not target_path.exists():
        logger.error(f"Target file not found: {target_path}")
        sys.exit(1)

    try:
        source_document = read_file(source_path)
        job_description = read_file(target_path)
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

    # Build plugin config from defaults + CLI overrides
    doc_type = args.doc_type
    plugin = get_plugin(doc_type)
    plugin_config = dict(plugin.default_plugin_config)
    if args.max_experiences is not None:
        plugin_config["max_experiences"] = args.max_experiences

    config = PipelineConfig(
        provider=provider,
        model_name=model_name,
        enable_research=args.research,
        plugin_config=plugin_config,
    )
    set_config(config)
    logger.info(f"Using {provider} / {model_name}")

    # Build and run the graph
    logger.info("Building pipeline...")
    app = build_graph(doc_type=doc_type)

    initial_state = {
        "doc_type": doc_type,
        "job_description": job_description,
        "source_document": source_document,
        "company_name": args.company,
        "target_role": args.role,
        "constraints": constraints,
    }

    logger.info("Running pipeline...")
    result = app.invoke(initial_state)

    # Output results
    tailored_output = result.get("tailored_output", "")
    evaluation = result.get("evaluation")

    if not tailored_output:
        logger.error("Pipeline produced no output")
        sys.exit(1)

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(tailored_output, encoding="utf-8")
    logger.info(f"Tailored output written to: {output_path}")

    # Print evaluation summary
    if evaluation:
        print("\n=== Evaluation Summary ===")
        print(f"Passed: {evaluation.passed}")
        print(f"Iterations: {result.get('iteration_count', 0)}")
        print("Scores:")
        for dim, score in evaluation.scores.items():
            status = "PASS" if score >= 7.0 else "FAIL"
            print(f"  {status} {dim}: {score:.1f}")
        if evaluation.critique:
            print(f"\nFeedback: {evaluation.critique}")

    print(f"\nOutput saved to: {output_path}")


if __name__ == "__main__":
    main()
