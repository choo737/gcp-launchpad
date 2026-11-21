# Tier-1 Architecture Router Questionnaire

Answer these eight sections to choose templates, compliance guardrails, team groups, and landing zone wiring.

Save answers in gitignored `platform-context.json` before creating private customer repositories.

## Section 1: Workload Scope

Which template capabilities do you need today?

- **Active templates**: `gcp-foundation`, `gcp-data-ingestion`, `gcp-data-medallion`, and `gcp-data-science`.
- **Planned roadmap templates**: `gcp-webapp` and `gcp-adk-agent`.

| Common Combination | Selected Templates | Typical Entry Mode |
| --- | --- | --- |
| Full Data Platform | `gcp-foundation` + `gcp-data-ingestion` + `gcp-data-medallion` | Greenfield |
| Full Data + Regulated ML | `gcp-foundation` + `gcp-data-ingestion` + `gcp-data-medallion` + `gcp-data-science` | Greenfield |
| Brownfield Ingestion + Medallion | `gcp-data-ingestion` + `gcp-data-medallion` | Brownfield |
| Brownfield Data Science | `gcp-data-science` | Brownfield |
| Medallion Only on Existing Bronze | `gcp-data-medallion` | Brownfield |

### Team Size Tier (`team_size_tier`)

Select `"S"`, `"M"`, or `"L"` to set CI separation and business-unit namespacing.

- **`"S"` (Pilot)**: Single deployer SA for small teams (`1-5` engineers).
- **`"M"` (Growth)**: Separate `tf_foundation_ci`, `tf_ingestion_ci`, and `dataform_ci` identities (`5-20` engineers).
- **`"L"` (Regulated SoD / Vendor Split)**: Per-stage foundation SAs (`org_gov_ci`, `net_sec_ci`, `data_plat_ci`) and `domain_name` namespaces.

## Section 2: Landing Zone Mode

Choose how your Google Cloud organization, network, and encryption keys are provisioned.

- **`greenfield`**: Deploy `gcp-foundation` to create folders, Shared VPC, Cloud KMS, BigQuery datasets, and WIF.
- **`brownfield`**: Reuse existing customer VPC, Cloud KMS key, buckets, and GCP projects.
- For `brownfield`, run `scripts/generate-brownfield-link.py` to build `00_linked.auto.tfvars.json` for `gcp-data-ingestion`.
- For `greenfield`, deploy `gcp-foundation` stages and chain outputs using `link-stages.sh`.

## Section 3: Compliance & Security Profile

Select one compliance profile for audit retention, key protection, FinOps, backups, NGFW, and SCC.

| Setting | `sandbox_poc` | `enterprise_standard` | `regulated_fsi_rmit` (BNM RMiT / FSI) |
| --- | --- | --- | --- |
| Audit Log Retention | `30` days | `1095` days | `2555` days |
| Audit Bucket Lock & Project Lien | `false` | `true` | `true` |
| Cloud KMS Protection | `SOFTWARE` | `SOFTWARE` | `HSM` |
| DR Region | `""` | `""` | `asia-southeast2` |
| Dedicated FinOps Project (`<prefix>-cmn-finops`) | `false` (`<prefix>-audit`) | `true` | `true` |
| Billing Export Location | `"US"` | `"US"` | `"asia-southeast1"` or `"US"` |
| Backup & DR Vault Retention | Disabled (`false`) | `14` days (`lock = false`) | `30` days (`lock = false`) |
| GCS Soft Delete Policy | `7` days | `14` days | `30` days |
| Cloud NGFW Tier | `Essentials` | `NGFW Standard` | `NGFW Standard` (`NGFW Enterprise` opt-in) |
| SCC Tier & Scope | `NONE` | `STANDARD` (`ORGANIZATION`/`FOLDER`/`PROJECT`) | `PREMIUM` + Runtime Detectors |
| VPC-SC | `Disabled` | `DRY_RUN` non-prod / `ENFORCED` prod | `DRY_RUN` non-prod / `ENFORCED` prod |

### Pillar 1: FinOps Governance & Billing Export

Isolate billing data and route multi-tier spend alerts to Google Groups.

- **`create_dedicated_finops_project`**: Use `<prefix>-cmn-finops` in `enterprise_standard` and `regulated_fsi_rmit`. Co-locate inside `<prefix>-audit` for `sandbox_poc`.
- **Architecture references**: Follow [Billing Export Setup](https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery-setup) and [Landing Zone Design](https://docs.cloud.google.com/docs/migration/plan/landing-zones).
- **`finops_billing_export_location` (`"US"` default)**: Choose `"US"` multi-region for automatic 2-month spend backfill per [Billing Export Guide](https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery).
- **`finops_billing_export_location` (`"asia-southeast1"` option)**: Choose `"asia-southeast1"` (forward-only) for strict metadata residency or direct joins with `<prefix>_ops_telemetry`.
- **Console toggle step**: Complete the one-time Cloud Console Billing Export toggle after Terraform creates the export dataset.
- **Budget controls**: Set `monthly_budget_amount`, `environment_budgets`, `department_budgets`, `workload_budgets`, `budget_thresholds` (`[0.5, 0.8, 0.9, 1.0]`), and `enable_forecasted_threshold`.
- **Department budgets (`department_budgets`)**: Split monthly caps across `data`, `ai`, `app`, and `shared` departments (`1500`, `1000`, `2000`, `500`).
- **Alert routing (`finops_alert_email_addresses`)**: Route alerts to `gcp-finops-alerts@<domain>` and `gcp-billing-admins@<domain>` (max 5 channels per budget).

### Pillar 2: Backup & Disaster Recovery

Protect stateful storage, BigQuery datasets, and compliance recovery objectives.

- **`enable_backup_dr`**: Provision central `<prefix>-cmn-backup` with an immutable `BackupVault`.
- **`backup_enforced_retention_days`**: Set `14` days for `enterprise_standard` or `30` days for `regulated_fsi_rmit`.
- **`lock_backup_vault` safety gate**: Keep irreversible WORM vault locking set to `false` by default until production cutover.
- **GCS `soft_delete_policy` (`soft_delete_retention_seconds`)**: Set `1209600` (`14d`) for `enterprise_standard` or `2592000` (`30d`) for `regulated_fsi_rmit`.
- **Dual-region GCS (`enable_dual_region_gcs`, `gcs_rpo`)**: Choose `DEFAULT` or `ASYNC_TURBO` (15-minute RPO SLA per [Cloud Storage SLA](https://cloud.google.com/storage/sla)).
- **FSI residency (`cross_border_dual_region_approved`)**: Confirm whether pairing `asia-southeast1` + `asia-southeast2` violates national border rules. Keep regional buckets if restricted.
- **GCS dual-region exclusions**: GCS excludes `asia-southeast2` and `asia-east2` from `ASIA` dual-regions; pair `["asia-southeast1", "asia-east1"]` or stay regional.
- **BigQuery DR (`bq_dr_mode`)**: Choose `time_travel_only`, `cross_region_replica` (`ALTER SCHEMA ... ADD REPLICA`), or `enterprise_plus_failover` instead of empty `*_dr` datasets.

### Pillar 3: Cloud NGFW & Network Security

Enforce layered firewall policies with IAM-governed workload tags.

- **`enable_hierarchical_firewall_policy` & `enable_ngfw_standard_rules`**: Combine a folder hierarchical firewall policy with a VPC global network policy.
- **`enable_secure_tags` (`GCE_FIREWALL`)**: Bind `tier=web`, `tier=app`, `tier=data`, and `access=allow-iap` tags instead of static IP lists.
- **Tier selection (`enable_ngfw_enterprise`)**: Default to `NGFW Standard`, or opt into `NGFW Enterprise` for regulated workloads.
- **Upgrade criteria (`NGFW Enterprise`)**: Enable only when workloads require deep-packet IPS signatures, CVE virtual patching, or inline TLS inspection.
- **Official references**: Review [Firewall Tiers](https://cloud.google.com/security/products/firewall) and [Firewall Pricing](https://cloud.google.com/firewall/pricing) before enabling enterprise inspection.

### Pillar 4: Security Command Center (SCC)

Configure threat detection, finding exports, and security operations routing.

- **`scc_tier`**: Choose `NONE`, `STANDARD`, or `PREMIUM`. Note that `SCC Enterprise` retires May 21, 2027.
- **`scc_scope`**: Choose `ORGANIZATION`, `FOLDER`, or `PROJECT` pay-as-you-go (`PAYG`) coverage.
- **`create_dedicated_secops_project`**: Set `true` for `<prefix>-cmn-secops` isolation, or `false` to colocate inside `<prefix>-audit`.
- **Organization ID (`organization_id`)**: Required for `PREMIUM` Security Posture or custom ETD modules even when `scc_scope = "FOLDER"`.
- **Audit KMS CMEK (`enable_audit_cmek`)**: Encrypt `<prefix>_scc_findings` BigQuery exports and Pub/Sub topics using Stage-01 Audit KMS keys.
- **Alert routing (`scc_alert_email_addresses`)**: Route high and critical SCC findings to `gcp-secops-alerts@<domain>`.
- **Runtime detectors (`runtime_detectors`)**: Select from `EVENT_THREAT_DETECTION`, `CONTAINER_THREAT_DETECTION`, `VIRTUAL_MACHINE_THREAT_DETECTION`, and `CLOUD_RUN_THREAT_DETECTION` when running `PREMIUM`.

## Section 4: Geography & Data Residency

Confirm where workloads and backup replicas must reside.

- **`primary_region`**: Default is `asia-southeast1` (Singapore).
- **`dr_region`**: Optional disaster recovery region such as `asia-southeast2` (Jakarta).
- Regulated FSI profiles should enable `dr_region` for cross-region KMS and BigQuery replication.

## Section 5: Environments & Naming

Define environment tiers and a company acronym so GCP project IDs stay within 30 characters.

- **`environments`**: Choose active tiers from `dev`, `uat`, `staging`, and `prod`.
- **Company / Organization Acronym (`prefix`)**: Use `3` to `6` lowercase chars (max `8`) matching `^[a-z][a-z0-9-]{1,6}[a-z0-9]$`.
- **Deterministic acronym rule**: Strip legal suffixes (`Bhd`, `Berhad`, `Sdn`, `Pte`, `Ltd`, `Inc`, `Corp`, `Holdings`, `Group`) when three core words remain.
- **Acronym examples**: Suggest `egr` for `'Example Global Retail Ltd'` and `sfg` for `'Sample Financial Group'`, then confirm.
- **`project_suffix` / `auto_unique_suffix`**: Set `project_suffix` (`<= 8` chars) or set `auto_unique_suffix = true` for a 4-char code.

## Section 6: GitOps & CI Identity

Specify the private GitHub target and CI authentication pattern.

- **`github_owner`**: Target private GitHub organization or owner handle such as `<YOUR_GITHUB_ORG>`.
- **`github_plan`**: Choose `github_free`, `github_team` (private `CODEOWNERS`), or `github_enterprise` (Environment Required Reviewers).
- **`ci_identity_mode`**: Choose `github_oidc_wif` for keyless GitHub Workload Identity Federation or `existing_ci_runner`.
- Always create private repositories with `gh repo create --private` before storing customer values.

## Section 7: Data Science & Regulated Explainable AI

Configure `gcp-data-science` for model training, explainable scoring, and BNM RMiT audit retention.

- **`enable_data_science`**: Set `true` to provision `data_science` tracks on top of Silver or Gold tables.
- **Vertex `:explain` sunset**: Vertex AI Explainable AI (`explanationSpec`) retires March 2027 per [Vertex AI Deprecations](https://cloud.google.com/vertex-ai/docs/deprecations).
- **Serving track (`ds_serving_track`)**: Choose `bqml_batch`, `vertex_cpr_online`, or `both` to avoid deprecated `:explain` APIs.
- **Track A (`bqml_batch`)**: Run batch training and `ML.EXPLAIN_PREDICT` in BigQuery per [BigQuery XAI Overview](https://cloud.google.com/bigquery/docs/xai-overview).
- **Track B (`vertex_cpr_online`)**: Serve real-time TreeSHAP attributions from Vertex AI Custom Prediction Routine (`CPR`) containers.
- **Project isolation (`team_size_tier`)**: Tier `S` shares one project. Tiers `M` and `L` isolate `ds-exp` from `ml-ops`.
- **Hardened Workbench (`enable_ds_workbench`)**: Enforce `disableRootAccess` and `disableFileDownloads` inside VPC-SC boundaries for regulated development.
- **Colab Enterprise (`enable_colab_enterprise`)**: Must stay `false` under `regulated_fsi_rmit`. Enable only for non-FSI `enterprise_standard` or `sandbox_poc`.
- **Online Feature Store (`enable_online_feature_store`)**: Uses Bigtable backing instead of `optimized` tier. Must stay `false` in `asia-southeast2`.
- **7-year BNM RMiT WORM ledger (`xai_audit_retention_days`)**: Set `>= 2555` days under `regulated_fsi_rmit` for `ml_xai_audit_ledger` and WORM buckets.
- **MRM `model-validator` gate**: Enforce `shap_additivity_tolerance` (`0.00001`, max `0.001`) and `fairness_min_disparate_impact` (`0.80`) before model promotion.

## Section 8: Enterprise Teams & Application Workloads

Configure 7-team Google Groups (`enterprise_teams`) and `gcp-foundation/apps/enterprise` workloads (`applications`).

- **7-Team Google Groups (`enterprise_teams`)**: Map `cloudops_admins_group`, `finops_admins_group`, `network_admins_group`, `security_admins_group`, `secops_analysts_group`, `data_admins_group`, `ai_admins_group`, and `app_admins_group`.
- **App factory (`applications`)**: Set `enable_apps`, `shared_artifact_registry`, and `workloads` (`display_name`, `enable_cloud_run`, `enable_gke`, `enable_cloud_sql`, `admin_group`, `developer_group`).

## Deterministic Agent Routing Table

AI coding agents must route confirmed questionnaire values to these exact targets:

| Context Block | Target Stage / Repo | Bridge / Link Command |
| --- | --- | --- |
| `finops`, `scc`, `backup_dr`, `ngfw`, `enterprise_teams` | `gcp-foundation/foundation/*` | `scripts/link-stages.sh --env <env>` |
| `existing_landing_zone` (`ingestion`) | `gcp-data-ingestion/stages/enterprise` | `generate-brownfield-link.py --target ingestion` |
| `data_science` + `existing_landing_zone` | `gcp-data-science/stages/enterprise` | `generate-brownfield-link.py --target data-science` |
| `applications` + `enterprise_teams.app_admins_group` | `gcp-foundation/apps/enterprise` | `generate-brownfield-link.py --target apps` |

## Output Contract (`platform-context.json`)

Write final answers to gitignored `platform-context.json` in the repository root.

- Copy `platform-context.json` into each cloned private template repository before running downstream setup skills.
- Review [examples/platform-context.greenfield.json](examples/platform-context.greenfield.json) for Greenfield defaults.
- Review [examples/platform-context.brownfield.json](examples/platform-context.brownfield.json) for Brownfield resource mappings.
