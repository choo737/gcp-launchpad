# Template Documentation Standard

This standard defines the shared structure, prose rules, and security checks across all `choo737` Google Cloud templates.

## Scope & Covered Repositories

Every active and planned template repository in the suite must follow this standard.

- **Active templates**: `gcp-launchpad`, `gcp-foundation`, `gcp-data-ingestion`, and `gcp-data-medallion`.
- **Planned templates**: `gcp-webapp` and `gcp-adk-agent`.
- Never create `GEMINI.md` or `catalog.yaml` in any repository; `README.md`, `AGENTS.md`, and `CLAUDE.md` serve as entry docs.

## Required Repository Files & Folders

| Path | Required Purpose |
| --- | --- |
| `README.md` | Canonical 10-section repository overview and single catalog entry point |
| `QUESTIONNAIRE.md` | Structured intake questionnaire mapping customer choices to config variables |
| `AGENTS.md` | Agent workflow rules for Antigravity, OpenAI Codex, Cursor, and Amp |
| `CLAUDE.md` | Concise Claude Code entry instructions referencing `AGENTS.md` and skills |
| `CODEOWNERS` | Default path-based reviewer rules for infrastructure, schemas, workflows, and docs |
| `LICENSE` | Apache License 2.0 text |
| `Makefile` | Standard `make test` and preflight/validation entry points |
| `.gitignore` | Blocks `platform-context.json`, `*.tfvars`, `*.tfvars.json`, and `*.tfstate*` |
| `.agents/skills/` | Task-specific agent skills with valid `SKILL.md` YAML frontmatter |
| `docs/` | Architecture guides, decision records, and 6-step Day-0/1/2 operational playbooks |
| `tests/` | Hermetic unit test suite verifying structure, schemas, workflows, and prose hygiene |

## Canonical 10-Section README.md Contract

Every template `README.md` must use these exact 10 `## ` headings in this exact order:

1. `## Template Suite Overview`: Single table summarizing `gcp-launchpad`, active templates, and planned `gcp-webapp` and `gcp-adk-agent`.
2. `## Create Your Private Repository (Do Not Fork Publicly)`: Exact `gh repo create --private --template` command and private-repo warning.
3. `## Architecture & Capabilities`: Technical Mermaid diagram plus concise Greenfield, Brownfield, and single-repo capability bullets.
4. `## 6-Step Enterprise Operationalization`: Short Day-0 -> Day-1 -> Day-2 summary linking to the repository operational guide under `docs/`.
5. `## AI Coding Agent Quickstart`: Copy-paste prompts (`Antigravity or OpenAI Codex` and `Claude Code`) plus a table of `.agents/skills/`.
6. `## CI/CD Workflows`: Summary of GitHub Actions checks, SHA-pinned actions, and offline PR validation.
7. `## Repository Layout`: Concise bullet map of key root files and top-level directories.
8. `## Quick Verification`: Standard `make` verification commands (`make preflight`, `make fmt-check`, `make validate`, `make test`).
9. `## Documentation Index`: Clickable links to `QUESTIONNAIRE.md`, `docs/`, and sibling suite guides.
10. `## License`: Apache License 2.0 reference linking to [LICENSE](../LICENSE).

## 6-Step Operationalization Guide Pattern

Each template `docs/` operational guide must walk teams cleanly from Day 0 to Day 2 in six steps:

1. **Step 1 (Day 0)**: Complete `QUESTIONNAIRE.md`, run preflight checks, and create private clones with `--private`.
2. **Step 2 (Day 0)**: Configure `CODEOWNERS`, branch protection, `dev`/`staging`/`prod` GitHub Environments, and keyless OIDC WIF.
3. **Step 3 (Day 1)**: Deploy foundational stages or link upstream outputs (`link-stages.sh` or `scripts/generate-brownfield-link.py`).
4. **Step 4 (Day 1)**: Promote `dev -> staging -> prod` with immutable digests, Secret Manager secrets, and protected release gates.
5. **Step 5 (Day 2)**: Provide a repeatable recipe to add new feeds, models, or workloads without editing core code.
6. **Step 6 (Day 2)**: Document telemetry triage, quarantine replay, drift-safe Terraform changes, and repository split triggers.

## Readability, Security & CI Enforcement

Hermetic tests in `tests/` must enforce every rule below on every pull request.

- **Prose readability**: Keep every Markdown sentence within `20` words, with zero decorative emojis, section symbols, or banned AI filler words.
- **Anti-leak hygiene**: Block real GCP project IDs, 12-digit org or folder IDs, hex billing IDs, secrets, and deprecated model IDs.
- **Neutral placeholders**: Use neutral tokens such as `example-org`, `<YOUR_ORG_ID>`, `<YOUR_FOLDER_ID>`, and `<YOUR_BILLING_ACCOUNT_ID>`.
- **CI hardening**: Pin all GitHub Actions to 40-character commit SHAs and forbid `${{ }}` interpolation inside `run:` blocks.
- **Keyless auth**: Authenticate cloud workflows through Workload Identity Federation (`WIF`) and run offline validation on pull requests.
