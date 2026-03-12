# Resume Tailor

LangGraph-powered pipeline that tailors a resume to a specific job description. Six-node pipeline with evaluation loopback — produces a targeted resume while enforcing baseline truth (no invented metrics or fabricated experience).

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
| `intake` | Validate inputs, clean text artifacts, parse resume into structured form | No |
| `research` | Web search for company context (optional) | Yes |
| `extract_and_match` | Build evidence map linking JD requirements → resume bullets | Yes |
| `select_content` | Decide suppressions + emphasis strategy | Partial — suppressions are deterministic, emphasis plan uses LLM |
| `generate` | Write the tailored resume with source annotations | Yes |
| `evaluate` | Score on 7 rubric dimensions + sanity checks, route loopback | Partial — sanity checks are deterministic, scoring uses LLM |

The **evidence map** is the central artifact. It's a structured mapping of every JD requirement to matching resume bullets, validated post-LLM to ensure all referenced bullets actually exist in the baseline resume.

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
# OpenAI (default)
OPENAI_API_KEY=your-key

# Gemini (free tier available)
GOOGLE_API_KEY=your-key
```

## Usage

```bash
# Basic usage (OpenAI) — accepts .txt, .pdf, or .docx
python main.py --resume resume.pdf --job job_posting.txt

# Gemini free tier
python main.py -r resume.docx -j job.txt --provider gemini

# With options
python main.py -r resume.txt -j job.txt \
  --provider gemini \
  --model gemini-2.5-pro \
  --company "Acme Corp" \
  --role "Senior Backend Engineer" \
  --output tailored.txt \
  --constraints '{"max_pages": 1, "tone": "technical"}' \
  --verbose
```

### CLI Flags

| Flag | Description |
|---|---|
| `-r, --resume` | Path to baseline resume (`.txt`, `.pdf`, `.docx`) — **required** |
| `-j, --job` | Path to job description (`.txt`, `.pdf`, `.docx`) — **required** |
| `-p, --provider` | LLM provider: `openai` (default) or `gemini` |
| `-m, --model` | Model name override (defaults: `gpt-4o`, `gemini-2.5-flash`) |
| `-c, --company` | Company name (enables richer research) |
| `--role` | Target role title |
| `-o, --output` | Output file path (default: `tailored_resume.txt`) |
| `--constraints` | JSON string for constraints (max_pages, tone, focus) |
| `--max-experiences` | Max experience blocks to keep (default: 4, 0 = no limit) |
| `--research` | Enable web research via Tavily (requires `TAVILY_API_KEY`) |
| `-v, --verbose` | Debug-level logging |

## Testing

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

## Project Structure

```
resume_tailor/
  state.py              # ResumeState TypedDict (graph state)
  models.py             # Pydantic domain models (EvidenceMap, etc.)
  config.py             # PipelineConfig + LLM provider factory
  graph.py              # Graph wiring + conditional routing
  nodes/                # One file per pipeline node
  prompts/              # Prompt templates (separated from node logic)
  parsers/              # File readers (txt/pdf/docx) + resume text → structured ParsedResume
  utils/
    validation.py       # Bullet matching, duplicate detection, sanity checks
tests/
  fixtures/             # Sample resume + job posting
main.py                 # CLI entry point
```

## Key Design Decisions

- **Evidence map is the spine** — every downstream decision traces back to it. Validated post-LLM with fuzzy matching (0.85 threshold via `SequenceMatcher`).
- **Baseline truth is a hard constraint** — source annotations link every output bullet to its origin. No invented numbers.
- **Suppressions are deterministic** — rule-based (no match → suppress, duplicate → keep strongest), not LLM-driven.
- **Scoped loopback** — evidence failures re-run `extract_and_match`, surface failures only re-run `generate`. Max 3 iterations.
- **Research is enrichment, not a dependency** — pipeline works well with just a JD and resume.
