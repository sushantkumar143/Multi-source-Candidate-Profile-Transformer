# Candidate Intelligence Pipeline

**Multi-source Candidate Profile Transformer**

A modular, scalable, and explainable data transformation pipeline that ingests candidate information from multiple heterogeneous sources, transforms it into a canonical candidate profile, resolves conflicts intelligently, tracks provenance, computes confidence scores, validates the schema, and generates configurable output.

---

## Architecture

```
Input Directory
     │
     ▼
┌──────────────────┐
│  Source Detector  │  Scans input dir, identifies file types
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────────────────┐
│                   PARSERS                         │
│  CSV │ Resume (PDF) │ GitHub (JSON) │ LinkedIn    │
│      │              │ (TXT)         │ Recruiter   │
│      │              │               │ Notes (TXT) │
└────────┬─────────────────────────────────────────┘
         │  ExtractedRecord[]
         ▼
┌──────────────────┐
│ Field Extractor   │  Maps raw fields → canonical names
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   Normalizer      │  Phones → E.164, Dates → YYYY-MM,
│                   │  Skills → canonical, Country → ISO-3166
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Merge Engine +   │  Combines sources, resolves conflicts
│  Conflict Resolver│  via scoring formula
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Canonical Profile │  ← Single source of truth
└────────┬─────────┘
         │
    ┌────┼────┐
    ▼    ▼    ▼
┌──────┐┌────────┐┌──────────┐
│Confid││Proven- ││Projection│  Config-driven output
│ence  ││ance   ││Engine    │  reshaping
└──┬───┘└───┬────┘└────┬─────┘
   └────────┼──────────┘
            ▼
    ┌───────────────┐
    │   Validator    │
    └───────┬───────┘
            │
       ┌────┴────┐
       ▼         ▼
  candidate  audit_report
    .json      .json
```

## Pipeline Stages

| # | Stage | Description |
|---|-------|-------------|
| 1 | Source Detection | Scan input directory, identify files, match parsers |
| 2 | Parsing | Extract raw data into `ExtractedRecord` objects |
| 3 | Field Extraction | Map raw field names to canonical names |
| 4 | Normalization | Phones → E.164, dates → YYYY-MM, skills → canonical, country → ISO-3166 |
| 5 | Merging | Combine data from all sources, resolve conflicts with scoring |
| 6 | Confidence | Compute per-field and overall confidence (deterministic, explainable) |
| 7 | Provenance | Track where each value came from and how it was derived |
| 8 | Projection | Apply runtime config to reshape output |
| 9 | Validation | Validate output against schema |
| 10 | Output | Write `candidate.json` + `audit_report.json` |

---

## Folder Structure

```
candidate_intelligence_pipeline/
├── app.py                          # CLI entry point (Typer)
├── pipeline.py                     # Pipeline orchestrator
├── config/
│   ├── settings.py                 # Source reliability, conflict weights, skill mapping
│   └── loader.py                   # Load & validate config.json
├── input/                          # Sample input files
│   ├── candidate.csv               # Structured source
│   ├── github_profile.json         # GitHub profile (simulated API response)
│   ├── linkedin.txt                # LinkedIn text export
│   ├── recruiter_notes.txt         # Free-text recruiter notes
│   ├── resume.pdf                  # PDF resume
│   └── config.json                 # Runtime config for output projection
├── output/                         # Generated outputs
├── schemas/
│   ├── extracted.py                # ExtractedRecord model
│   ├── canonical.py                # CanonicalProfile model
│   ├── config_schema.py            # RuntimeConfig model
│   └── output_schema.py            # Output validation
├── parsers/
│   ├── base.py                     # Abstract BaseParser
│   ├── csv_parser.py               # CSV structured parser
│   ├── resume_parser.py            # PDF resume parser
│   ├── github_parser.py            # GitHub profile parser
│   ├── linkedin_parser.py          # LinkedIn text parser
│   ├── recruiter_notes_parser.py   # Recruiter notes parser
│   └── registry.py                 # Parser registry (plug-and-play)
├── extractors/
│   └── field_extractor.py          # Raw → canonical field mapping
├── normalizers/
│   ├── phone_normalizer.py         # Phone → E.164
│   ├── date_normalizer.py          # Date → YYYY-MM
│   ├── skill_normalizer.py         # Skill → canonical name
│   ├── location_normalizer.py      # Country → ISO-3166 alpha-2
│   └── deduplicator.py             # Remove duplicates
├── merger/
│   ├── merge_engine.py             # Multi-source merge logic
│   └── conflict_resolver.py        # Score-based conflict resolution
├── confidence/
│   └── confidence_engine.py        # Deterministic confidence scoring
├── provenance/
│   └── provenance_tracker.py       # Field-level provenance tracking
├── projector/
│   └── projection_engine.py        # Config-driven output projection
├── validator/
│   └── schema_validator.py         # Output validation
├── audit/
│   └── audit_engine.py             # Audit report generation
├── utils/
│   ├── logger.py                   # Structured logging
│   └── helpers.py                  # Shared utilities
├── tests/
│   ├── test_phone_normalizer.py
│   ├── test_merge_engine.py
│   ├── test_confidence_engine.py
│   ├── test_projection_engine.py
│   └── test_pipeline_e2e.py
├── requirements.txt
└── README.md
```

---

## How to Run

### Prerequisites
- Python 3.11+
- pip

### Installation
```bash
pip install -r requirements.txt
```

### Generate Sample Resume (first time)
```bash
pip install reportlab
python generate_resume.py
```

### Run the Pipeline
```bash
# Default (all canonical fields, auto-discovers config.json)
python app.py --input input/

# With explicit config
python app.py --input input/ --config input/config.json

# With custom output directory
python app.py --input input/ --output results/

# With debug logging
python app.py --input input/ --log-level DEBUG
```

### Run Tests
```bash
pytest tests/ -v
```

---

## Canonical Profile Schema

| Field | Type | Notes |
|-------|------|-------|
| `candidate_id` | `string` | Deterministic SHA-256 hash |
| `full_name` | `string` | |
| `emails` | `string[]` | Deduplicated, lowercase |
| `phones` | `string[]` | E.164 format |
| `location` | `{city, region, country}` | Country: ISO-3166 alpha-2 |
| `links` | `{linkedin, github, portfolio, other[]}` | |
| `headline` | `string \| null` | |
| `years_experience` | `number \| null` | Computed from experience dates |
| `skills` | `[{name, confidence, sources[]}]` | Canonical skill names |
| `experience` | `[{company, title, start, end, summary}]` | Dates as YYYY-MM |
| `education` | `[{institution, degree, field, end_year}]` | |
| `provenance` | `[{field, source, method}]` | Where each value came from |
| `overall_confidence` | `number` | 0.0 – 1.0 |

---

## Runtime Configuration

The config file reshapes the output without changing the canonical profile:

```json
{
  "fields": [
    { "path": "full_name", "type": "string", "required": true },
    { "path": "primary_email", "from": "emails[0]", "type": "string", "required": true },
    { "path": "phone", "from": "phones[0]", "type": "string", "normalize": "E164" },
    { "path": "skills", "from": "skills[].name", "type": "string[]", "normalize": "canonical" }
  ],
  "include_confidence": true,
  "on_missing": "null"
}
```

Supported features:
- **Field selection**: Only include specified fields
- **Renaming**: `path` = output key, `from` = canonical source path
- **Path expressions**: `emails[0]`, `skills[].name`, `location.city`
- **Per-field normalization**: `E164`, `canonical`
- **Missing value policy**: `null`, `omit`, `error`
- **Confidence/provenance toggle**: `include_confidence`, `include_provenance`

---

## Conflict Resolution

When sources disagree, a scoring engine selects the best value:

```
Score = SourceReliability × 0.35
      + AgreementBonus    × 0.30
      + ExtractionConf    × 0.25
      - ConflictPenalty   × 0.10
```

**Source Reliability Scores:**

| Source | Reliability | Rationale |
|--------|-----------|-----------|
| LinkedIn | 0.85 | Self-reported but curated |
| CSV | 0.80 | Structured but may be stale |
| GitHub | 0.75 | Public, verifiable via repos |
| Resume | 0.70 | Unstructured, extraction imprecise |
| Recruiter Notes | 0.50 | Informal, subjective |

**Example:**
- Resume says "Google", CSV says "Amazon", Recruiter Notes says "Google"
- Google: reliability=0.70, agreement=2/3=67%, extraction=0.65 → Score: 0.575
- Amazon: reliability=0.80, agreement=1/3=33%, extraction=0.90 → Score: 0.523
- **Selected: Google** (reason: Resume and Recruiter Notes agreed)

---

## Confidence Scoring

Per-field confidence is computed from 5 deterministic factors:

| Factor | Weight | Description |
|--------|--------|-------------|
| Source reliability | 0.30 | Max reliability among contributing sources |
| Agreement ratio | 0.30 | Proportion of sources that agree |
| Extraction confidence | 0.20 | Average extraction quality from parsers |
| Normalization success | 0.10 | Whether normalization succeeded |
| Conflict-free | 0.10 | No conflicts detected for this field |

**Overall confidence** = weighted mean of field confidences × completeness factor

---

## Extensibility

Adding a new parser (e.g., IndeedParser):

1. Create `parsers/indeed_parser.py` implementing `BaseParser`
2. Register it in `parsers/registry.py`'s `create_default_registry()`

That's it — no other code changes needed.

---

## Sample Input

The `input/` directory contains sample data for a candidate **Priya Sharma** with deliberate conflicts:

| Source | Company | Skills | Phone |
|--------|---------|--------|-------|
| CSV | Amazon | Python, Java, AWS, Docker | 9876543210 |
| Resume PDF | Google → Amazon | Python, Java, SQL, Spark, K8s, Docker, AWS, TF, ML, Git, CI/CD, REST, PostgreSQL | +91 98765 43210 |
| GitHub JSON | — | Python, Go, JavaScript, Shell (from repos) | — |
| LinkedIn TXT | Google → Amazon | Python, ML, Spark, K8s, Docker, AWS, Data Eng, TF, SQL, Git | — |
| Recruiter Notes | Google (currently) | Python, TF, Spark, AWS, Docker, K8s | 9876543210 |

The conflict on `current_company` (Amazon vs Google) is resolved by the scoring engine — Google wins because 3/4 sources agree.

---

## Sample Output

See `output/candidate.json` and `output/audit_report.json` after running the pipeline.

---

## Assumptions

1. **Single candidate per run**: The pipeline processes one candidate at a time. CSV is expected to have one row.
2. **Local files only**: GitHub profile is a local JSON file simulating an API response. Live API integration is a future extension.
3. **Default phone region**: Phones without country code are assumed to be Indian (+91). Configurable in `config/settings.py`.
4. **Skill canonicalization**: Unknown skills are title-cased. The canonical mapping covers 120+ common tech skills.
5. **Date parsing**: Ambiguous dates are parsed with `PREFER_DATES_FROM=past`. Months default to January when only year is provided.

---

## Edge Cases Handled

1. **Missing source files**: Pipeline runs with available sources; logs warnings for missing files
2. **Broken/empty PDF**: Returns empty record, pipeline continues
3. **Invalid CSV columns**: Maps available columns, warns about unmapped ones
4. **Unparseable phone numbers**: Keeps raw value, sets normalization_success=false
5. **Conflicting dates**: Uses dateparser with best-effort; keeps raw on failure
6. **Empty fields**: Tracked as missing in audit, never invented

---

## Future Improvements

- **Live API integration**: GitHub REST/GraphQL API, LinkedIn OAuth
- **Multi-candidate batch processing**: Process CSV with many rows
- **Entity resolution**: Match candidates across runs (dedup at candidate level)
- **ML-based extraction**: Use NER models for resume parsing instead of regex
- **Webhook support**: Trigger pipeline on new source file uploads
- **Database backend**: Store canonical profiles in PostgreSQL
- **Web UI**: Visual pipeline dashboard with audit trail viewer
