# Template Documentation Standard

This standard defines the shared 5-Act progressive layout, prose rules, and automated cross-repo gates across all `choo737` templates.

## Scope & Covered Repositories

Every active and planned template repository in the suite must follow this standard.

- **Active templates**: `gcp-launchpad`, `gcp-foundation`, `gcp-data-ingestion`, `gcp-data-medallion`, and `gcp-data-science`.
- **Planned templates**: `gcp-webapp` and `gcp-adk-agent`.
- Never create `GEMINI.md` or `catalog.yaml`.

## Required Repository Files & Folders

| Path | Required Purpose |
| --- | --- |
| `README.md` | Canonical 5-Act progressive overview (`~65` header lines + 3 `<details open>` drawers) |
| `QUESTIONNAIRE.md` | Structured `## Section 1..N:` intake questionnaire mapping choices to variables |
| `AGENTS.md` | Primary agent rules (`# AGENTS.md`) with `## Cross-Repo Documentation Invariant` |
| `CLAUDE.md` | Concise Claude Code entry file (`# CLAUDE.md`, `## Quick Rules`) pointing to `AGENTS.md` |
| `CODEOWNERS` | Default path-based reviewer rules for infrastructure, schemas, workflows, and docs |
| `LICENSE` | Apache License 2.0 text |
| `Makefile` | Standard `make help` and `make test` entry points (`make audit-suite` in `gcp-launchpad`) |
| `.gitignore` | Blocks `platform-context.json`, Terraform state, and `*.auto.tfvars*` files |
| `.agents/skills/` | Task-specific agent skills with valid `SKILL.md` YAML frontmatter |
| `docs/` | Architecture guides and 6-step Day-0 through Day-2 operational playbooks |
| `tests/suite_doc_contract.py` | Byte-identical SHA-locked contract module shared across all 5 repositories |

## Canonical 5-Act Progressive README.md Contract

1. **Line 1 Suite Breadcrumb Bar**: Links `00 Launchpad` through `04 Data Science`, bolding the active repo.
2. **Hero Diagram**: `<img src="assets/cloud-city-<slug>.webp" alt="..." width="100%">` (`1676 px` lossless `2x`, no duplicate in-image H1).
3. **Five Ordered `## ` Headings**:
   - `## Quick Orientation`: 3-row scenario picker (`gcp-launchpad`) or 4-column stage contract (`01` through `04`).
   - `## Start in 3 Steps`: Private clone (`example-org/<repo>` + `isPrivate` check), 1 AI prompt, and local `make` verification.
   - `## Platform Districts`: Byte-identical 4-column suite table across all 5 repositories.
   - `## Technical Reference`: Exactly 3 `<details open>` drawers (`1. Architecture...`, `2. Prerequisites...`, `3. Repository Layout...`).
   - `## License`: Exact line `Apache License 2.0. See [LICENSE](LICENSE).`

## Automated Cross-Repository Uniformity Gate

- **Per-repo unit test**: Every repo runs `validate_repo_suite_contract(...)` from `tests/suite_doc_contract.py` during `make test`.
- **Cross-repo SHA & drift gate**: `python3 scripts/audit-suite-uniformity.py` (`make audit-suite`) checks local `../gcp-*` siblings or live GitHub `main` branches.
- **Sentence & cell cap**: Keep every Markdown sentence and table cell within `20` words.
- **Anti-leak hygiene**: Forbid emojis, section symbols, banned filler words, 12-digit IDs, billing IDs, and deprecated models.
- **CI hardening**: Pin all GitHub Actions to 40-character commit SHAs and forbid `${{ }}` inside `run:` blocks.
