# AGENTS.md

`gcp-launchpad` is the entry router for the `choo737` Google Cloud template suite.

## Template Catalog

Read [README.md](README.md) as the single template catalog.

Never create `catalog.yaml`.

- Active templates: `gcp-foundation`, `gcp-data-ingestion`, `gcp-data-medallion`.
- Planned templates: `gcp-webapp`, `gcp-adk-agent`.

## Routing & Bridge Workflow

1. Walk the user through [QUESTIONNAIRE.md](QUESTIONNAIRE.md) before cloning repositories or running cloud commands.
2. Run `scripts/preflight-check.sh` to verify local tools, active `gcloud` identity, and GitHub CLI auth.
3. Save answers to gitignored `platform-context.json` matching `examples/platform-context.greenfield.json` or `examples/platform-context.brownfield.json`.
4. Always create private customer repositories using `gh repo create <owner>/<repo> --private --template choo737/<template> --clone`.
5. For Brownfield setups, run `scripts/generate-brownfield-link.py` to produce `00_linked.auto.tfvars.json` (`0600`).

## Security & Prose Rules

- Never commit `platform-context.json`, `*.tfvars`, `*.tfvars.json`, or `*.tfstate*`.
- Never commit real GCP project IDs, 12-digit org or folder IDs, billing IDs, or personal LDAPs.
- Use `<YOUR_ORG_ID>`, `<YOUR_FOLDER_ID>`, `<YOUR_BILLING_ACCOUNT_ID>`, and `example-org` in docs and examples.
- Keep every Markdown sentence within `20` words without decorative emojis, section symbols, or AI filler words.

## Available Skills

- `.agents/skills/route-architecture/SKILL.md`
- `.agents/skills/brownfield-bridge/SKILL.md`

## Verification

```bash
make preflight
make test
```
