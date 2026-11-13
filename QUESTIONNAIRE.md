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

Select one compliance profile for audit retention, key protection, threat detection, and perimeter enforcement.

| Setting | `sandbox_poc` | `enterprise_standard` | `regulated_fsi_rmit` (BNM RMiT / FSI) |
| --- | --- | --- | --- |
| Audit Log Retention | `30` days | `1095` days | `2555` days |
| Audit Bucket Lock & Project Lien | `false` | `true` | `true` |
| Cloud KMS Protection | `SOFTWARE` | `SOFTWARE` | `HSM` |
| DR Region | `""` | `""` | `asia-southeast2` |
| SCC Tier | `NONE` | `STANDARD` | `PREMIUM` + Security Posture |
| VPC-SC | `Disabled` | `DRY_RUN` non-prod / `ENFORCED` prod | `DRY_RUN` non-prod / `ENFORCED` prod |

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
