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
2. Run `scripts/preflight-check.sh` to verify local tools, active `gcloud` identity, and GitHub CLI auth.
3. Save answers to gitignored `platform-context.json` matching `examples/platform-context.greenfield.json` or `examples/platform-context.brownfield.json`.
4. Always create private customer repositories using `gh repo create <owner>/<repo> --private --template choo737/<template> --clone`.
5. For Brownfield setups, run `scripts/generate-brownfield-link.py` (`--target ingestion` or `--target data-science`) for `00_linked.auto.tfvars.json` (`0600`).
6. Follow [docs/01-end-to-end-operational-playbook.md](docs/01-end-to-end-operational-playbook.md) for cross-repository Day-0, Day-1, and Day-2 handoffs.

## Security & Prose Rules

- Never commit `platform-context.json`, `terraform.tfvars`, `*.auto.tfvars`, `*.auto.tfvars.json`, or `*.tfstate*`.
- Never commit real GCP project IDs, 12-digit org or folder IDs, billing IDs, or personal LDAPs.
- Use `<YOUR_ORG_ID>`, `<YOUR_FOLDER_ID>`, `<YOUR_BILLING_ACCOUNT_ID>`, and `example-org` in docs and examples.
- Follow [docs/02-template-documentation-standard.md](docs/02-template-documentation-standard.md) for README structure, `<= 20`-word sentences, and CI hardening.

## Available Skills

- `.agents/skills/route-architecture/SKILL.md`
- `.agents/skills/brownfield-bridge/SKILL.md`

## Verification

```bash
make preflight
make test
```
