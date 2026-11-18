---
name: brownfield-bridge
description: Inspects existing GCP landing zone resources with read-only gcloud commands, updates platform-context.json, and generates brownfield tfvars and Dataform settings.
---

# Brownfield Bridge

Use this workflow when skipping `gcp-foundation` and deploying onto an existing Google Cloud landing zone.

## Step 1: Discover Existing GCP Resources (Read-Only)

Run read-only `gcloud` and `bq` commands to inspect existing projects, networks, keys, buckets, and datasets:

```bash
gcloud compute networks list --project <network-project-id>
gcloud compute networks subnets list --project <network-project-id> --regions <region>
gcloud compute network-attachments list --project <network-project-id> --regions <region>
gcloud kms keys list --location <region> --keyring <keyring> --project <governance-project-id>
bq ls --project_id <core-project-id>
gcloud storage buckets list --project <core-project-id>
gcloud backup-dr backup-vaults list --location <region> --project <backup-project-id>
gcloud dataform repositories list --location <region> --project <compute-project-id>
gcloud dataplex datascans list --location <region> --project <analytics-project-id>
gcloud workbench instances list --location <region>-a --project <ds-exp-project-id>
gcloud ai endpoints list --region <region> --project <ml-ops-project-id>
gcloud artifacts repositories list --location <region> --project <ml-ops-project-id>
```

Never guess resource IDs, service account emails, or policy tag paths.

## Step 2: Confirm and Update `platform-context.json`

1. Confirm every discovered ID with the user before writing files.
2. Populate `existing_landing_zone` inside gitignored `platform-context.json`.
3. Include required fields: `core_project_id`, `compute_project_id`, `bronze_dataset_id`, `landing_bucket_name`, and `dataform_repository_name`.
4. Add `by_environment` (`dev`, `staging`, `prod`) inside `existing_landing_zone` when environments use distinct projects or buckets.
5. Add optional `Dataform`, `Dataplex`, and `Datastream` fields (`dataform_release_config_name`, `dataplex_profile_scan_id`, `dataplex_quality_scan_id`, `datastream_network_attachment_id`).
6. Add optional `BackupVault`, `KMS`, VPC, and policy tag fields (`backup_project_id`, `backup_vault_id`, `kms_key_id`, `vpc_id`, `subnet_id`, `pii_restricted_policy_tag_id`, `pii_masked_policy_tag_id`).
7. Add Data Science fields (`ds_exp_project_id`, `ml_ops_project_id`, `ml_artifact_repo_id`, `ml_audit_dataset_id`, `ml_audit_table_id`, `ml_worm_bucket_name`, `silver_dataset_id`) when linking `gcp-data-science`.

## Step 3: Generate `00_linked.auto.tfvars.json` for Ingestion or Data Science

Run `scripts/generate-brownfield-link.py` with `--env` targeting `gcp-data-ingestion/stages/enterprise`:

```bash
python3 scripts/generate-brownfield-link.py \
  --context platform-context.json \
  --env dev \
  --target-variables-tf ../<customer-ingestion-repo>/stages/enterprise/variables.tf \
  --output ../<customer-ingestion-repo>/stages/enterprise/00_linked.auto.tfvars.json
```

Run with `--target data-science` targeting `gcp-data-science/stages/enterprise` and pass `--no-manage-kms-iam --print-kms-commands` if KMS admins bind IAM separately:

```bash
python3 scripts/generate-brownfield-link.py \
  --context platform-context.json \
  --env dev \
  --target data-science \
  --no-manage-kms-iam \
  --print-kms-commands \
  --target-variables-tf ../<customer-ds-repo>/stages/enterprise/variables.tf \
  --output ../<customer-ds-repo>/stages/enterprise/00_linked.auto.tfvars.json
```

Verify the generated file has mode `0600` and contains only declared variables.

## Step 4: Configure `gcp-data-medallion` Compilation Inputs

Map the same confirmed IDs into `gcp-data-medallion`:

1. Update `workflow_settings.yaml` defaults (`defaultProject`, `defaultLocation`, `defaultDataset`, `defaultAssertionDataset`).
2. Copy `envs/<env>.compilation.json.example` to gitignored compilation overrides or Dataform release variables.
3. Set `bronze_project`, `bronze_dataset`, `silver_project`, `silver_dataset`, `gold_project`, `gold_dataset`, and PII policy tags.
