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
4. Confirm `adoption_mode`, `compliance_profile`, `primary_region`, `dr_region`, `environments`, `prefix` (`3` to `8` chars), `project_suffix`, `github_owner`, and `ci_identity_mode`.
5. Collect Pillar 1 `finops` inputs (`create_dedicated_finops_project`, `finops_billing_export_location`, budgets, `budget_thresholds`, `enable_forecasted_threshold`, and `finops_alert_email_addresses`).
6. Collect Pillar 2 `backup_dr` inputs (`enable_backup_dr`, `backup_enforced_retention_days`, `lock_backup_vault`, `soft_delete_retention_seconds`, `enable_dual_region_gcs`, `gcs_rpo`, `cross_border_dual_region_approved`, and `bq_dr_mode`).
7. Collect Pillar 3 `ngfw` inputs (`enable_hierarchical_firewall_policy`, `enable_ngfw_standard_rules`, `enable_secure_tags`, and `enable_ngfw_enterprise`).
8. Collect Pillar 4 `scc` inputs (`scc_tier`, `scc_scope`, `enable_audit_cmek`, `scc_alert_email_addresses`, and `runtime_detectors`).
9. Never guess org IDs, folder IDs, billing IDs, or project names.

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
