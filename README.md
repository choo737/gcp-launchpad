# GCP Launchpad

`gcp-launchpad` is the starting repo for the `choo737` Google Cloud template set.

Use it to map requirements, inspect existing GCP projects, and spin up private repositories.

## Template Suite Overview

<img src="assets/cloud-city-launchpad.webp" alt="Four-layer Google Cloud platform overview" width="100%">

Each repository owns one layer: `01` foundation, `02` ingestion, `03` warehouse, and `04` apps and agents.
Together they fit into a single Google Cloud environment without overlapping ownership.

| Template Repository | Status | Included Capabilities | Best For |
| --- | --- | --- | --- |
| **gcp-launchpad** *(this repo)* | Active | Intake questionnaire, preflight checks, Brownfield bridge, and playbook | Multi-repo planning and team handoffs |
| [gcp-foundation](https://github.com/choo737/gcp-foundation) | Active | Landing Zone, Folders, Shared VPC, VPC-SC, KMS, SCC, Audit Logs, BigQuery, WIF | Greenfield orgs, regulated FSI, or brownfield folders |
| [gcp-data-ingestion](https://github.com/choo737/gcp-data-ingestion) | Active | Datastream CDC, Pub/Sub Streaming + DLQ, Cloud Run Batch ELT, Workflows, Composer 3 | Greenfield linked or standalone Brownfield zones |
| [gcp-data-medallion](https://github.com/choo737/gcp-data-medallion) | Active | Dataform `3.1.5` SQLX Medallion, Dual-Tier PII Tags, Dataplex Auto DQ, Tag Promotion | Greenfield or standalone Brownfield BigQuery Bronze |
| `gcp-webapp` *(Planned)* | Roadmap | HA Web App with HTTPS Load Balancer, Cloud Armor, Cloud Run, Cloud SQL | Customer portals on Greenfield or Brownfield VPCs |
| `gcp-adk-agent` *(Planned)* | Roadmap | Google ADK Agent on Agent Engine or Cloud Run with Eval Gate | Enterprise AI agents routed via runtime choice |

## Create Your Private Repository (Do Not Fork Publicly)

GitHub forces normal forks of public repositories to stay public.

Always create private customer repositories with `--private` before saving `platform-context.json` or cloning downstream templates.

```bash
gh repo create <org>/gcp-launchpad --private --template choo737/gcp-launchpad --clone
cd gcp-launchpad
gh repo view --json isPrivate --jq '.isPrivate'
```

Confirm `gh repo view` prints `true` before storing any customer identifiers.

## Architecture & Capabilities

Teams can start in `gcp-launchpad` for multi-repo platforms or adopt one downstream template directly.

```mermaid
flowchart TD
    A["Start in gcp-launchpad or Single Template Repo"] --> B{"Adoption Entry Path"}
    B -- "Guided Multi-Repo" --> C["Complete QUESTIONNAIRE.md"]
    C --> D["Run scripts/preflight-check.sh"]
    D --> E["Save gitignored platform-context.json"]
    E --> F["Create private repos via gh repo create --private"]
    F --> G{"Landing Zone Mode"}
    G -- "Greenfield" --> H["Deploy gcp-foundation and run link-stages.sh"]
    G -- "Brownfield" --> I["Run scripts/generate-brownfield-link.py"]
    H --> J["Deploy gcp-data-ingestion and gcp-data-medallion"]
    I --> J
    B -- "Direct Single-Repo" --> K["Open repo standalone QUESTIONNAIRE.md"]
    K --> L["Follow repo setup skill in private clone"]
```

- **Greenfield `link-stages.sh`**: Deploy `gcp-foundation` first, then run `link-stages.sh` to export outputs into downstream stages.
- **Brownfield `scripts/generate-brownfield-link.py`**: Skip `gcp-foundation` and write `00_linked.auto.tfvars.json` (`0600`) from existing landing zone IDs.
- **Single-repo adoption**: Each template keeps its own standalone `QUESTIONNAIRE.md` for direct adoption without `gcp-launchpad`.

## 6-Step Enterprise Operationalization

Follow the full cross-repository runbook in [docs/01-end-to-end-operational-playbook.md](docs/01-end-to-end-operational-playbook.md).

1. **Step 1 (Day 0)**: Complete [QUESTIONNAIRE.md](QUESTIONNAIRE.md), run `scripts/preflight-check.sh`, and write gitignored `platform-context.json`.
2. **Step 2 (Day 0)**: Create private repositories (`--private`), set `CODEOWNERS` and branch protection, and scope keyless GitHub WIF (`ci_repository_map`).
3. **Step 3 (Day 1)**: Deploy `gcp-foundation` (`00-bootstrap` -> `01-org-governance` -> `02-security-network` -> `data/enterprise/*`). For Brownfield, run `scripts/generate-brownfield-link.py`.
4. **Step 4 (Day 1)**: Deploy `gcp-data-ingestion` across `dev -> staging -> prod` with immutable loader digests and Secret Manager credentials.
5. **Step 5 (Day 1)**: Deploy `gcp-data-medallion` via PR dry-runs and cut an annotated `v1.0.0` Git tag to promote `prod-main`.
6. **Step 6 (Day 2)**: Onboard new business feeds across Ingestion (`tfvars` maps) and Medallion (`01_bronze`..`03_gold`). Update Foundation (`additional_quality_scans` or Gold domains) when needed.

## AI Coding Agent Quickstart

### Antigravity or OpenAI Codex

```text
Read AGENTS.md, QUESTIONNAIRE.md, and .agents/skills/route-architecture/SKILL.md.
Guide me through the intake questions, run scripts/preflight-check.sh, and write platform-context.json.
Create private customer repositories using gh repo create --private --template choo737/<template>.
```

### Claude Code

```text
Read CLAUDE.md, QUESTIONNAIRE.md, and .agents/skills/route-architecture/SKILL.md.
Help me choose Greenfield or Brownfield mode and generate gitignored platform-context.json.
For Brownfield setups, load .agents/skills/brownfield-bridge/SKILL.md and generate 00_linked.auto.tfvars.json.
```

| Skill | File | Purpose |
| --- | --- | --- |
| `route-architecture` | `.agents/skills/route-architecture/SKILL.md` | Guides intake questions, runs preflight checks, writes `platform-context.json`, and creates private repos |
| `brownfield-bridge` | `.agents/skills/brownfield-bridge/SKILL.md` | Inspects existing GCP resources, updates `platform-context.json`, and generates `00_linked.auto.tfvars.json` |

## CI/CD Workflows

Every push to `main` and every pull request runs `.github/workflows/ci.yml` on `ubuntu-latest`.

- Action references in `.github/workflows/ci.yml` are pinned to full 40-character commit SHAs.
- The workflow uses read-only `contents: read` permissions and avoids `${{ }}` interpolation inside `run:` blocks.
- CI executes `make preflight` (offline dry-run) and `make test` (structure, schema, prose, and security unit tests).

## Repository Layout

- `assets/`: Cloud City visual architecture animations and org completeness scanner diagram.
- `QUESTIONNAIRE.md`: Six-section Tier-1 intake questionnaire producing gitignored `platform-context.json`.
- `docs/`: End-to-end operational playbook and template documentation standard.
- `examples/`: Reference `platform-context.greenfield.json` and `platform-context.brownfield.json` contracts.
- `scripts/`: `preflight-check.sh` validator and `generate-brownfield-link.py` tfvars bridge (`0600`).
- `.agents/skills/`: Agent skills for `route-architecture` and `brownfield-bridge`.
- `CODEOWNERS`: Default repository reviewer ownership rules for template and workflow files.
- `tests/`: Hermetic Python `unittest` suite enforcing structure, scripts, schemas, CI hardening, and prose rules.

## Quick Verification

```bash
make preflight
make test
```

## Documentation Index

- [Tier-1 Architecture Router Questionnaire](QUESTIONNAIRE.md)
- [End-to-End Operational Playbook](docs/01-end-to-end-operational-playbook.md)
- [Template Documentation Standard](docs/02-template-documentation-standard.md)
- [Org Completeness Scanner Design](docs/03-org-completeness-scanner-design.md)
- [gcp-foundation Enterprise Operationalization Guide](https://github.com/choo737/gcp-foundation/blob/main/docs/05-enterprise-operationalization-guide.md)
- [gcp-data-ingestion Enterprise Adoption Guide](https://github.com/choo737/gcp-data-ingestion/blob/main/docs/03-enterprise-adoption-guide.md)
- [gcp-data-medallion Enterprise Operationalization Guide](https://github.com/choo737/gcp-data-medallion/blob/main/docs/02-enterprise-operationalization-guide.md)

## License

Licensed under the Apache License 2.0 ([LICENSE](LICENSE)).
