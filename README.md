# Doc Tailor

LangGraph-powered framework for tailoring documents to target specifications. Six-node pipeline with evaluation loopback — produces targeted output while enforcing baseline truth (no invented metrics or fabricated claims).

Ships with a **resume plugin** out of the box. Extensible to cover letters, proposals, grant applications, or any "adapt document X to audience Y" task via the plugin system.

## Architecture

```
intake → research (optional) → extract_and_match → select_content → generate → evaluate
                                       ↑                                          |
                                       |_____ evidence failure ___________________|
                                                                                  |
                                       generate ←── surface failure ──────────────┘
                                                                                  |
                                       END ←── pass or max retries ───────────────┘
```

**Nodes:**

| Node | Purpose | LLM? |
|---|---|---|
| `intake` | Validate inputs, clean text artifacts, parse source document via plugin | No |
| `research` | Web search for company context (optional, Tavily) | Yes |
| `extract_and_match` | Build evidence map linking target requirements → source document segments | Yes |
| `select_content` | Decide suppressions + emphasis strategy | Partial — suppressions are deterministic (plugin), emphasis plan uses LLM |
| `generate` | Write the tailored output with source annotations | Yes |
| `evaluate` | Score on 7 rubric dimensions + sanity checks, route loopback | Partial — sanity checks are deterministic, scoring uses LLM |

The **evidence map** is the central artifact. It's a structured mapping of every requirement to matching source text, validated post-LLM to ensure all referenced segments actually exist in the source document.

## Plugin System

Each document type is a plugin that provides:

| Component | What it does |
|---|---|
| `parse_source` | Parses raw text into a structured model |
| `get_matchable_text` | Returns all citable text segments |
| `prompts` | All prompt templates for the document type |
| `compute_suppressions` | Deterministic content selection logic |
| `parse_output` | Extracts tailored output + annotations from LLM response |
| `sanity_checks` | Document-type-specific evaluation checks |

To add a new document type, create a plugin in `doc_tailor/plugins/` and call `register_plugin()`. See `doc_tailor/plugins/resume/` for the reference implementation.

## Setup

```bash
pip install -e .

# For PDF and DOCX input support
pip install -e ".[parsers]"
```

Copy `.env.example` to `.env` and add your API key(s):

```bash
cp .env.example .env
```

```
# OpenRouter — unified gateway to every frontier + open-weight model
OPENROUTER_API_KEY=your-key
```

All LLM calls route through [OpenRouter](https://openrouter.ai), which exposes Claude, GPT, Gemini, Llama, Gemma, Qwen, DeepSeek, etc. behind one OpenAI-compatible endpoint. Get a key at [openrouter.ai/keys](https://openrouter.ai/keys), browse models at [openrouter.ai/models](https://openrouter.ai/models).

## Usage

```bash
# Basic usage (resume tailoring) — accepts .txt, .pdf, or .docx
python main.py --source resume.pdf --target job_posting.txt

# Backwards-compatible aliases
python main.py --resume resume.pdf --job job_posting.txt

# Pick a specific model (any OpenRouter slug works)
python main.py --source resume.docx --target job.txt --model anthropic/claude-sonnet-4.6

# With options
python main.py --source resume.txt --target job.txt \
  --doc-type resume \
  --model google/gemma-4-31b-it \
  --company "Acme Corp" \
  --role "Senior Backend Engineer" \
  --output tailored.txt \
  --constraints '{"max_pages": 1, "tone": "technical"}' \
  --verbose
```

### Model picks

| Tier | Slug | Notes |
|---|---|---|
| Cheap / open | `google/gemma-4-31b-it` (default) | Open-weight, fast, strong value |
| Balanced | `anthropic/claude-haiku-4.5` | Quality jump for eval/critique loop |
| Quality | `anthropic/claude-sonnet-4.6` or `google/gemini-3-pro` | Frontier-tier |

### CLI Flags

| Flag | Description |
|---|---|
| `--source, --resume, -r` | Path to source document (`.txt`, `.pdf`, `.docx`) — **required** |
| `--target, --job, -j` | Path to target specification (`.txt`, `.pdf`, `.docx`) — **required** |
| `--doc-type` | Document type plugin to use (default: `resume`) |
| `-m, --model` | OpenRouter model slug (default: `google/gemma-4-31b-it`) |
| `-c, --company` | Company name (enables richer research) |
| `--role` | Target role title |
| `-o, --output` | Output file path (default: `output/tailored_output.txt`) |
| `--constraints` | JSON string for constraints (max_pages, tone, focus) |
| `--max-experiences` | Max experience blocks to keep (resume plugin, default: 4, 0 = no limit) |
| `--research` | Enable web research via Tavily (requires `TAVILY_API_KEY`) |
| `-v, --verbose` | Debug-level logging |

## Testing

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

## Project Structure

```
doc_tailor/
  plugin.py               # DocumentTypePlugin + DocumentPrompts + registry
  state.py                # TailoringState TypedDict (generic graph state)
  models.py               # Generic Pydantic models (EvidenceMap, etc.)
  config.py               # PipelineConfig + OpenRouter-backed LLM factory
  graph.py                # Graph wiring + conditional routing
  nodes/                  # Generic node implementations (delegate to plugin)
  prompts/                # Generic prompt fragments
  parsers/                # File readers (txt/pdf/docx)
  utils/
    validation.py         # Text matching, duplicate detection, sanity checks
  plugins/
    resume/               # Resume document type plugin
      models.py           # ResumeBullet, ExperienceBlock, ParsedResume
      parser.py           # Plain-text resume → structured ParsedResume
      prompts.py          # Resume-specific prompt templates
      content.py          # Experience block scoring + bullet target suppression
      validation.py       # Verb tense consistency, annotation validation
tests/
  fixtures/               # Sample resume + job posting
main.py                   # CLI entry point
```