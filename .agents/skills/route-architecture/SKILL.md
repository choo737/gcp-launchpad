---
name: route-architecture
description: Guides users through QUESTIONNAIRE.md, runs preflight checks, writes platform-context.json, creates private customer repositories, and hands off deployment.
---

# Route Architecture

Follow these steps to route a customer from intake to private template repositories.

## Step 1: Run Intake Questionnaire

1. Read `README.md` and `QUESTIONNAIRE.md` with the user.
2. Confirm workload scope across `gcp-foundation`, `gcp-data-ingestion`, `gcp-data-medallion`, and `gcp-data-science`.
3. Note planned roadmap templates (`gcp-webapp`, `gcp-adk-agent`) if requested for future phases.
4. Confirm `adoption_mode`, `compliance_profile`, `primary_region`, `dr_region`, `environments` (`dev`, `uat`, `prod`), `github_owner`, and `ci_identity_mode`.
5. Suggest a `3-6` char company acronym `prefix` (strip `Ltd`, `Group`), and confirm with the user.
6. Set `auto_unique_suffix = true` (or `1-4` char `project_suffix`) for `prj-<env>-<workload>-<hash4>` project IDs (`coe`, `dev`, `uat`, `prod`).
7. Collect Pillar 1 `finops` inputs (`create_dedicated_finops_project`, `finops_billing_export_location`, `department_budgets`, budgets, `budget_thresholds`, `enable_forecasted_threshold`, and `finops_alert_email_addresses`).
8. Collect Pillar 2 `backup_dr` inputs (`enable_backup_dr`, `backup_enforced_retention_days`, `lock_backup_vault`, `soft_delete_retention_seconds`, `enable_dual_region_gcs`, `gcs_rpo`, `cross_border_dual_region_approved`, and `bq_dr_mode`).
9. Collect Pillar 3 `ngfw` inputs (`enable_hierarchical_firewall_policy`, `enable_ngfw_standard_rules`, `enable_secure_tags`, and `enable_ngfw_enterprise`).
10. Collect Pillar 4 `scc` inputs (`scc_tier`, `scc_scope`, `create_dedicated_secops_project`, `enable_audit_cmek`, `scc_alert_email_addresses`, and `runtime_detectors`).
11. Collect Section 7 `data_science` inputs (`enable_data_science`, `ds_serving_track`, `enable_ds_workbench`, `enable_colab_enterprise`, `enable_online_feature_store`, `xai_audit_retention_days`, `shap_additivity_tolerance`, and `fairness_min_disparate_impact`).
12. Collect Section 8 `enterprise_teams` (7-team Google Groups) and `applications` (`enable_apps`, `shared_artifact_registry`, `workloads`) inputs.
13. Reject `enable_colab_enterprise = true` under `regulated_fsi_rmit`, and reject `enable_online_feature_store = true` in `asia-southeast2`.
14. Never guess org IDs, folder IDs, billing IDs, or project names.

- **Folder hierarchy**: Use `fldr-coe`, top-level `fldr-network`, and `fldr-environments` (`fldr-prod`, `fldr-uat`, `fldr-dev`) with merged `data-core`.
- **Team subfolders**: Use `fldr-<env>-data-platform`, `fldr-<env>-ai-platform`, and `fldr-<env>-app-platform` (`fldr-<env>-<key>`).

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
2. Open that repository's `QUESTIONNAIRE.md` and `setup-*` skill (`setup-customer-foundation`, `setup-data-ingestion`, `setup-data-science`, or medallion skills).
3. For `greenfield`, deploy `gcp-foundation` first and run `scripts/link-stages.sh`.
4. For `brownfield`, generate `00_linked.auto.tfvars.json` using `scripts/generate-brownfield-link.py` (`--target ingestion`, `--target data-science`, or `--target apps`).
