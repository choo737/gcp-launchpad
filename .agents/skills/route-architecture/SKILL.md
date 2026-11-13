---
name: route-architecture
description: Guides users through QUESTIONNAIRE.md, runs preflight checks, writes platform-context.json, creates private customer repositories, and hands off deployment.
---

# Route Architecture

Follow these steps to route a customer from intake to private template repositories.

## Step 1: Run Intake Questionnaire

1. Read `README.md` and `QUESTIONNAIRE.md` with the user.
2. Confirm workload scope across `gcp-foundation`, `gcp-data-ingestion`, and `gcp-data-medallion`.
3. Note planned roadmap templates (`gcp-webapp`, `gcp-adk-agent`) if requested for future phases.
4. Confirm `adoption_mode` (`greenfield` or `brownfield`), `compliance_profile`, `primary_region`, `dr_region`, `environments`, `prefix`, `project_suffix`, and `github_owner`.
5. Never guess org IDs, folder IDs, billing IDs, or project names.

## Step 2: Run Preflight Checks

Run `scripts/preflight-check.sh` with any known `--project`, `--folder`, or `--org` flags:

```bash
bash scripts/preflight-check.sh --org <YOUR_ORG_ID>
```

Verify active `gcloud` credentials and `gh auth status` before creating repositories.

## Step 3: Write `platform-context.json`

1. Write validated answers to gitignored `platform-context.json` at the repository root.
2. Match the schema in `examples/platform-context.greenfield.json` or `examples/platform-context.brownfield.json`.
3. If `adoption_mode` is `brownfield`, also follow `.agents/skills/brownfield-bridge/SKILL.md`.

## Step 4: Create Private Customer Repositories

Never fork templates publicly or store customer parameters in public repositories.

```bash
gh repo create <owner>/<customer-repo> --private --template choo737/<template> --clone
cd <customer-repo>
gh repo view --json isPrivate --jq '.isPrivate'
```

Confirm `gh repo view` prints `true` for every created repository.

## Step 5: Hand Off Context

1. Copy `platform-context.json` into each cloned private repository root.
2. Open that repository's `QUESTIONNAIRE.md` and `setup-*` skill (`setup-customer-foundation`, `setup-data-ingestion`, or medallion skills).
3. For `greenfield`, deploy `gcp-foundation` first and run `scripts/link-stages.sh`.
4. For `brownfield`, generate `stages/enterprise/00_linked.auto.tfvars.json` using `scripts/generate-brownfield-link.py`.
