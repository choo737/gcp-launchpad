# GEMINI.md

Follow [AGENTS.md](AGENTS.md) and [README.md](README.md) when routing workloads across the `choo737` template suite.

## Quick Rules

- Load [.agents/skills/route-architecture/SKILL.md](.agents/skills/route-architecture/SKILL.md) to run [QUESTIONNAIRE.md](QUESTIONNAIRE.md) and write `platform-context.json`.
- Load [.agents/skills/brownfield-bridge/SKILL.md](.agents/skills/brownfield-bridge/SKILL.md) to inspect existing GCP projects and run `scripts/generate-brownfield-link.py`.
- Route active templates (`gcp-foundation`, `gcp-data-ingestion`, `gcp-data-medallion`) and planned templates (`gcp-webapp`, `gcp-adk-agent`).
- Keep [README.md](README.md) as the single catalog and never create `catalog.yaml`.
- Always create private repositories via `gh repo create --private` and never commit `platform-context.json` or `*.tfvars`.
- Validate changes with `scripts/preflight-check.sh --dry-run`, `make preflight`, and `make test`.
