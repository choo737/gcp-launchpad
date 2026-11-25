# AGENTS.md

`gcp-launchpad` is the entry router for the `choo737` Google Cloud template suite.

## Template Catalog & Documentation

Read [README.md](README.md) as the single template catalog.

Never create `GEMINI.md` or `catalog.yaml`.

- Active templates: `gcp-foundation`, `gcp-data-ingestion`, `gcp-data-medallion`, `gcp-data-science`.
- Planned templates: `gcp-webapp`, `gcp-adk-agent`.
- Operational playbook: [docs/01-end-to-end-operational-playbook.md](docs/01-end-to-end-operational-playbook.md).
- Documentation standard: [docs/02-template-documentation-standard.md](docs/02-template-documentation-standard.md).
- Org scanner design: [docs/03-org-completeness-scanner-design.md](docs/03-org-completeness-scanner-design.md).

## Routing & Bridge Workflow

1. Walk the user through [QUESTIONNAIRE.md](QUESTIONNAIRE.md) before cloning repositories or running cloud commands.
2. Derive and suggest a `3-6` char company acronym `prefix` (strip legal suffixes like `Ltd`, `Group`), then confirm.
3. Run `scripts/preflight-check.sh` to verify local tools, active `gcloud` identity, and GitHub CLI auth.
4. Save answers to gitignored `platform-context.json` matching `examples/platform-context.greenfield.json` or `examples/platform-context.brownfield.json`.
5. Set `auto_unique_suffix = true` when no `1-4` char `project_suffix` is given for `prj-<env>-<workload>-<hash4>` project IDs.
6. Always create private customer repositories using `gh repo create example-org/<repo> --private --template choo737/<template> --clone`.
7. For Brownfield setups, run `scripts/generate-brownfield-link.py` (`--target ingestion`, `--target data-science`, or `--target apps`) (`0600`).
8. Follow [docs/01-end-to-end-operational-playbook.md](docs/01-end-to-end-operational-playbook.md) for cross-repository Day-0, Day-1, and Day-2 handoffs.

## Folder & Environment Standard

- Environments: `dev`, `uat`, and `prod`.
- Top-level folders: `fldr-coe`, `fldr-network`, and `fldr-environments` (`fldr-prod`, `fldr-uat`, `fldr-dev`).
- Tier subfolders: `fldr-<env>-data-platform`, `fldr-<env>-ai-platform`, and `fldr-<env>-app-platform` (`fldr-<env>-<key>`).

## Cross-Repo Documentation Invariant

- Keep `tests/suite_doc_contract.py` byte-identical across all five `choo737/gcp-*` repositories.
- Run `scripts/audit-suite-uniformity.py` across sibling repos before pushing shared doc or `Makefile` edits.

## Security & Prose Rules

- Never commit `platform-context.json`, `terraform.tfvars`, `*.auto.tfvars`, `*.auto.tfvars.json`, or `*.tfstate*`.
- Never commit real GCP project IDs, 12-digit org or folder IDs, billing IDs, or personal LDAPs.
- Use `<YOUR_ORG_ID>`, `<YOUR_FOLDER_ID>`, `<YOUR_BILLING_ACCOUNT_ID>`, and `example-org` in docs and examples.
- Follow [docs/02-template-documentation-standard.md](docs/02-template-documentation-standard.md) for the 5-Act `README.md`, `<= 20`-word cap, and CI hardening.

## Available Skills

- `.agents/skills/route-architecture/SKILL.md`
- `.agents/skills/brownfield-bridge/SKILL.md`

## Verification

```bash
make preflight
make test
make audit-suite
```
