# CLAUDE.md

Read [AGENTS.md](AGENTS.md) and [README.md](README.md) before guiding a customer architecture or cloning templates.

## Quick Rules

- Load [.agents/skills/route-architecture/SKILL.md](.agents/skills/route-architecture/SKILL.md) for intake routing and private repo provisioning.
- Load [.agents/skills/brownfield-bridge/SKILL.md](.agents/skills/brownfield-bridge/SKILL.md) when skipping `gcp-foundation` on an existing landing zone.
- Use [QUESTIONNAIRE.md](QUESTIONNAIRE.md) to select `gcp-foundation`, `gcp-data-ingestion`, `gcp-data-medallion`, `gcp-webapp`, or `gcp-adk-agent`.
- Follow [docs/01-end-to-end-operational-playbook.md](docs/01-end-to-end-operational-playbook.md) for cross-repo Day-0 through Day-2 rollout steps.
- Follow [docs/02-template-documentation-standard.md](docs/02-template-documentation-standard.md) for the canonical 10-section `README.md` and prose rules.
- Never create `GEMINI.md` or `catalog.yaml`; [README.md](README.md) is the single template catalog.
- Write answers to gitignored `platform-context.json` and bridge Brownfield inputs with `scripts/generate-brownfield-link.py`.
- Create private customer repositories with `gh repo create --private` before storing any configuration.
- Run `scripts/preflight-check.sh`, `make preflight`, and `make test` after edits.
