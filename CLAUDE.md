# CLAUDE.md

Read [AGENTS.md](AGENTS.md) and [README.md](README.md) before guiding a customer architecture or cloning templates.

## Quick Rules

- Load [.agents/skills/route-architecture/SKILL.md](.agents/skills/route-architecture/SKILL.md) for intake routing and private repo provisioning.
- Load [.agents/skills/brownfield-bridge/SKILL.md](.agents/skills/brownfield-bridge/SKILL.md) when skipping `gcp-foundation` on an existing landing zone.
- Use [QUESTIONNAIRE.md](QUESTIONNAIRE.md) to select `gcp-foundation`, `gcp-data-ingestion`, `gcp-data-medallion`, `gcp-data-science`, `gcp-webapp`, or `gcp-adk-agent`.
- Follow [docs/01-end-to-end-operational-playbook.md](docs/01-end-to-end-operational-playbook.md) for cross-repo Day-0 through Day-2 rollout steps.
- Follow [docs/02-template-documentation-standard.md](docs/02-template-documentation-standard.md) and keep `tests/suite_doc_contract.py` synced across all five repos.
- Follow [docs/03-org-completeness-scanner-design.md](docs/03-org-completeness-scanner-design.md) for read-only org scanner checks (`D00` through `D16`).
- Never create `GEMINI.md` or `catalog.yaml`; [README.md](README.md) is the single template catalog.
- Never commit `platform-context.json`, `terraform.tfvars`, `*.auto.tfvars`, `*.auto.tfvars.json`, or `*.tfstate*`.
- Suggest a `3-6` lowercase char company acronym `prefix` (e.g. `'Example Global Retail Ltd'` -> `egr`) and confirm.
- Set `auto_unique_suffix = true` (or `1-4` char `project_suffix`) for `prj-<env>-<workload>-<hash4>` project IDs (`coe`, `dev`, `uat`, `prod`).
- Include `dev`, `uat`, and `prod` environments plus `enterprise_teams` and `applications` when routing.
- Use top-level `fldr-coe`, `fldr-network`, and `fldr-environments` (`fldr-prod`, `fldr-uat`, `fldr-dev`) with merged `data-core`.
- Use tier subfolders `fldr-<env>-data-platform`, `fldr-<env>-ai-platform`, and `fldr-<env>-app-platform` (`fldr-<env>-<key>`).
- Write answers to gitignored `platform-context.json` and bridge Brownfield inputs with `scripts/generate-brownfield-link.py` (`ingestion`, `data-science`, `apps`).
- Create private customer repositories with `gh repo create example-org/<repo> --private` before storing any configuration.
- Run `scripts/preflight-check.sh`, `make test`, and `make audit-suite` after edits.
