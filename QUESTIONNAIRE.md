# Tier-1 Architecture Router Questionnaire

Answer these six sections to choose templates, compliance guardrails, and landing zone wiring.

Save answers in gitignored `platform-context.json` before creating private customer repositories.

## Section 1: Workload Scope

Which template capabilities do you need today?

- **Active templates**: `gcp-foundation`, `gcp-data-ingestion`, and `gcp-data-medallion`.
- **Planned roadmap templates**: `gcp-webapp` and `gcp-adk-agent`.

| Common Combination | Selected Templates | Typical Entry Mode |
| --- | --- | --- |
| Full Data Platform | `gcp-foundation` + `gcp-data-ingestion` + `gcp-data-medallion` | Greenfield |
| Brownfield Ingestion + Medallion | `gcp-data-ingestion` + `gcp-data-medallion` | Brownfield |
| Medallion Only on Existing Bronze | `gcp-data-medallion` | Brownfield |

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
| SCC Tier & Scope | `NONE` | `STANDARD` (org/folder) | `PREMIUM` + Runtime Detectors |
| VPC-SC | `Disabled` | `DRY_RUN` non-prod / `ENFORCED` prod | `DRY_RUN` non-prod / `ENFORCED` prod |

### Pillar 1: FinOps Governance & Billing Export

Isolate billing data and route multi-tier spend alerts to Google Groups.

- **`create_dedicated_finops_project`**: Use `<prefix>-cmn-finops` in `enterprise_standard` and `regulated_fsi_rmit`. Co-locate inside `<prefix>-audit` for `sandbox_poc`.
- **Architecture references**: Follow [Billing Export Setup](https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery-setup) and [Landing Zone Design](https://docs.cloud.google.com/docs/migration/plan/landing-zones).
- **`billing_export_location` (`"US"` default)**: Choose `"US"` multi-region for automatic 2-month spend backfill per [Billing Export Guide](https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery).
- **`billing_export_location` (`"asia-southeast1"` option)**: Choose `"asia-southeast1"` (forward-only) for strict metadata residency or direct SQL joins with `<prefix>_ops_telemetry`.
- **Console toggle step**: Complete the one-time Cloud Console Billing Export toggle after Terraform creates the export dataset.
- **Multi-budget map**: Define `master`, `dev`/`staging`/`prod`, and workload budgets with `50/80/90/100%` actual and `100%` forecasted thresholds.
- **Alert routing**: Route alerts to `gcp-finops-alerts@<domain>`, `gcp-billing-admins@<domain>`, and `<team>-owners@<domain>` (max 5 channels per budget) plus Pub/Sub.

### Pillar 2: Backup & Disaster Recovery

Protect stateful storage, BigQuery datasets, and compliance recovery objectives.

- **`enable_backup_dr`**: Provision central `<prefix>-cmn-backup` with an immutable `BackupVault` (`14d` standard / `30d` FSI enforced retention).
- **`lock_backup_vault` safety gate**: Keep irreversible WORM vault locking set to `false` by default until production cutover.
- **GCS `soft_delete_policy`**: Set `14d` for `enterprise_standard` or `30d` for `regulated_fsi_rmit`.
- **GCS dual-region `rpo`**: Choose `DEFAULT` or `ASYNC_TURBO` (contractual 15-minute RPO SLA per [Cloud Storage SLA](https://cloud.google.com/storage/sla)).
- **FSI check 1 (SLA proof)**: Confirm whether critical buckets require contractual `RPO <= 15m` audit proof.
- **FSI check 2 (BNM RMiT residency)**: Confirm whether pairing `asia-southeast1` + `asia-southeast2` violates national border residency rules. If restricted, keep single-region buckets and a regional `BackupVault`.
- **BigQuery DR**: Use `168h` time travel plus 7d fail-safe as baseline. Add opt-in `ALTER SCHEMA ... ADD REPLICA` or `ENTERPRISE_PLUS` failover instead of empty `*_dr` shell datasets.

### Pillar 3: Cloud NGFW & Network Security

Enforce layered firewall policies with IAM-governed workload tags.

- **2-layer policy**: Combine a `Folder Hierarchical Firewall Policy` with a `VPC Global Network Firewall Policy`.
- **`GCE_FIREWALL` IAM Secure Tags**: Bind `tier=web`, `tier=app`, `tier=data`, and `access=allow-iap` tags instead of brittle IP lists.
- **Tier selection**: Use `Essentials` (`sandbox_poc`), `NGFW Standard` default (`enterprise_standard`), or opt in via `enable_ngfw_enterprise`.
- **Upgrade criteria (`NGFW Enterprise`)**: Enable only when workloads require deep-packet IPS signatures, CVE virtual patching, or inline TLS inspection.
- **Official references**: Review [Firewall Tiers](https://cloud.google.com/security/products/firewall) and [Firewall Pricing](https://cloud.google.com/firewall/pricing) before enabling enterprise inspection.

### Pillar 4: Security Command Center (SCC)

Configure threat detection, finding exports, and security operations routing.

- **Tier selection**: Choose `NONE`, `STANDARD`, or `PREMIUM`. Note that `SCC Enterprise` retires May 21, 2027.
- **`scc_scope`**: Choose organization or folder activation versus project-level `PREMIUM` pay-as-you-go (`PAYG`) coverage.
- **Audit KMS CMEK**: Encrypt `<prefix>_scc_findings` BigQuery exports and Pub/Sub topics using Stage-01 Audit KMS CMEK keys.
- **Alert routing**: Route high and critical SCC findings to `gcp-secops-alerts@<domain>`.
- **Runtime threat detectors**: Enable Event, Container, VM, and Cloud Run Threat Detection when running `PREMIUM`.

## Section 4: Geography & Data Residency

Confirm where workloads and backup replicas must reside.

- **`primary_region`**: Default is `asia-southeast1` (Singapore).
- **`dr_region`**: Optional disaster recovery region such as `asia-southeast2` (Jakarta).
- Regulated FSI profiles should enable `dr_region` for cross-region KMS and BigQuery replication.

## Section 5: Environments & Naming

Define environment tiers and short naming tokens so GCP project IDs stay within 30 characters.

- **`environments`**: Choose active tiers from `dev`, `staging`, and `prod`.
- **`prefix`**: Use 2 to 8 lowercase characters matching `^[a-z][a-z0-9-]{1,7}$`.
- **`project_suffix`**: Use up to 8 characters such as `dev01` to prevent soft-delete ID collisions.

## Section 6: GitOps & CI Identity

Specify the private GitHub target and CI authentication pattern.

- **`github_owner`**: Target private GitHub organization or owner handle such as `<YOUR_GITHUB_ORG>`.
- **`ci_identity_mode`**: Choose `github_oidc_wif` for keyless GitHub Workload Identity Federation or `existing_ci_runner`.
- Always create private repositories with `gh repo create --private` before storing customer values.

## Output Contract (`platform-context.json`)

Write final answers to gitignored `platform-context.json` in the repository root.

- Copy `platform-context.json` into each cloned private template repository before running downstream setup skills.
- Review [examples/platform-context.greenfield.json](examples/platform-context.greenfield.json) for Greenfield defaults.
- Review [examples/platform-context.brownfield.json](examples/platform-context.brownfield.json) for Brownfield resource mappings.
