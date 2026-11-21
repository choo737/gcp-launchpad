#!/usr/bin/env python3
"""Generate 00_linked.auto.tfvars.json for brownfield ingestion, data-science, or apps."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

PROJECT_ID_RE = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
DATASET_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
BUCKET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$")
ENVIRONMENT_RE = re.compile(r"^(dev|uat|staging|prod)$")
PREFIX_RE = re.compile(r"^[a-z][a-z0-9-]{1,6}[a-z0-9]$")
PROJECT_SUFFIX_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,6}[a-z0-9])?$")
BILLING_ACCOUNT_RE = re.compile(r"^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$")
FOLDER_ID_RE = re.compile(r"^(?:folders/)?[0-9]{6,25}$")
DOMAIN_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,19}[a-z0-9]$")
GCS_URI_RE = re.compile(r"^gs://[a-z0-9][a-z0-9._-]{1,61}[a-z0-9](/.*)?$")
REGION_RE = re.compile(r"^[a-z]+-[a-z]+[0-9]+$")
DATAFORM_SHORT_RE = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
DATAFORM_PATH_RE = re.compile(
    r"^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/locations/[a-z0-9-]+/repositories/[A-Za-z0-9_-]{1,100}$"
)
RELEASE_CONFIG_PATH_RE = re.compile(
    r"^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/locations/[a-z0-9-]+/repositories/[A-Za-z0-9_-]{1,100}/releaseConfigs/[A-Za-z0-9_-]{1,100}$"
)
DATAPLEX_SCAN_SHORT_RE = re.compile(r"^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$")
DATAPLEX_SCAN_PATH_RE = re.compile(
    r"^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/locations/[a-z0-9-]+/dataScans/[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)
SA_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
KMS_KEY_RE = re.compile(
    r"^projects/([a-z][a-z0-9-]{4,28}[a-z0-9])/locations/([a-z0-9-]+)/keyRings/([A-Za-z0-9._-]+)/cryptoKeys/([A-Za-z0-9._-]+)$"
)
VPC_ID_RE = re.compile(
    r"^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/global/networks/[A-Za-z0-9._-]+$"
)
SUBNET_ID_RE = re.compile(
    r"^projects/([a-z][a-z0-9-]{4,28}[a-z0-9])/regions/([a-z0-9-]+)/subnetworks/([A-Za-z0-9._-]+)$"
)
NETWORK_ATTACHMENT_RE = re.compile(
    r"^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/regions/[a-z0-9-]+/networkAttachments/[A-Za-z0-9._-]+$"
)
POLICY_TAG_RE = re.compile(
    r"^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/locations/[a-z0-9-]+/taxonomies/[0-9]+/policyTags/[0-9]+$"
)
ARTIFACT_REGISTRY_URI_RE = re.compile(
    r"^[a-z0-9-]+-docker\.pkg\.dev/[a-z][a-z0-9-]{4,28}[a-z0-9]/[a-z0-9][a-z0-9._-]{0,62}$"
)
BACKUP_VAULT_ID_RE = re.compile(
    r"^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/locations/[a-z0-9-]+/backupVaults/[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$"
)
TABLE_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
ML_ARTIFACT_REPO_SHORT_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")
ML_ARTIFACT_REPO_PATH_RE = re.compile(
    r"^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/locations/[a-z0-9-]+/repositories/[a-z0-9][a-z0-9._-]{0,62}$"
)
TF_VAR_DECL_RE = re.compile(r'^\s*variable\s+"([A-Za-z0-9_]+)"\s*\{', re.MULTILINE)

DS_SERVING_TRACKS = frozenset({"bqml_batch", "vertex_cpr_online", "both"})
PROJECT_DELETION_POLICIES = frozenset({"PREVENT", "DELETE", "ABANDON"})
LEGAL_ENTITY_SUFFIXES = frozenset({
    "bhd",
    "berhad",
    "sdn",
    "pte",
    "ltd",
    "limited",
    "inc",
    "incorporated",
    "corp",
    "corporation",
    "llc",
    "llp",
    "plc",
    "co",
    "company",
})
OPTIONAL_GROUP_SUFFIXES = frozenset({"holdings", "holding", "group"})
ENTERPRISE_TEAMS_KEYS = frozenset({
    "cloudops_admins_group",
    "finops_admins_group",
    "network_admins_group",
    "security_admins_group",
    "secops_analysts_group",
    "data_admins_group",
    "ai_admins_group",
    "app_admins_group",
})
APPLICATIONS_KEYS = frozenset({
    "enable_apps",
    "shared_artifact_registry",
    "workloads",
})
APPLICATION_WORKLOAD_KEYS = frozenset({
    "display_name",
    "enable_cloud_run",
    "enable_gke",
    "enable_cloud_sql",
    "admin_group",
    "developer_group",
})
DATA_SCIENCE_CONFIG_KEYS = frozenset({
    "enable_data_science",
    "ds_serving_track",
    "enable_ds_workbench",
    "enable_colab_enterprise",
    "enable_online_feature_store",
    "xai_audit_retention_days",
    "shap_additivity_tolerance",
    "fairness_min_disparate_impact",
})

REQUIRED_FIELDS = (
    "core_project_id",
    "compute_project_id",
    "bronze_dataset_id",
    "landing_bucket_name",
    "dataform_repository_name",
)

DATA_SCIENCE_REQUIRED_FIELDS = (
    "ds_exp_project_id",
    "ml_ops_project_id",
)

APPS_REQUIRED_FIELDS = (
    "prefix",
    "region",
    "environment",
)

FIELD_FLAGS = (
    "core_project_id",
    "compute_project_id",
    "analytics_project_id",
    "bi_project_id",
    "governance_project_id",
    "finops_project_id",
    "backup_project_id",
    "backup_vault_id",
    "bronze_dataset_id",
    "silver_dataset_id",
    "gold_dataset_id",
    "quarantine_dataset_id",
    "assertions_dataset_id",
    "landing_bucket_name",
    "ops_telemetry_dataset_id",
    "dataform_repository_name",
    "dataform_release_config_name",
    "dataform_sa_email",
    "batch_loader_sa_email",
    "pubsub_writer_sa_email",
    "dataplex_profile_scan_id",
    "dataplex_quality_scan_id",
    "kms_key_id",
    "pii_restricted_policy_tag_id",
    "pii_masked_policy_tag_id",
    "vpc_id",
    "subnet_id",
    "datastream_network_attachment_id",
    "artifact_registry_repository_uri",
    "region",
    "environment",
    "prefix",
    "domain_name",
)

DATA_SCIENCE_FIELD_FLAGS = (
    "ds_exp_project_id",
    "ml_ops_project_id",
    "ml_artifact_repo_id",
    "ml_audit_dataset_id",
    "ml_audit_table_id",
    "ml_worm_bucket_name",
    "egress_connector_subnet_id",
    "ds_serving_track",
)

APPS_FIELD_FLAGS = (
    "billing_account",
    "project_suffix",
    "app_folder_id",
    "shared_vpc_host_project_id",
    "shared_artifact_registry_id",
    "app_admins_group",
    "project_deletion_policy",
)

BOOLEAN_LANDING_ZONE_KEYS = frozenset({"manage_kms_iam"})

ALIAS_PAIRS = (
    ("core_project_id", "core_storage_project_id"),
    ("compute_project_id", "etl_compute_project_id"),
    ("analytics_project_id", "primary_gold_project_id"),
    ("gold_dataset_id", "primary_gold_dataset_id"),
    ("dataform_release_config_name", "dataform_release_config_id"),
    ("kms_key_id", "kms_key_name"),
    ("vpc_id", "network_id"),
    ("dataform_sa_email", "dataform_service_account_email"),
)

ALIAS_RHS_TO_LHS = {alias: primary for primary, alias in ALIAS_PAIRS}
VALID_LANDING_ZONE_KEYS = (
    frozenset(FIELD_FLAGS)
    | frozenset(DATA_SCIENCE_FIELD_FLAGS)
    | frozenset(APPS_FIELD_FLAGS)
    | frozenset(ALIAS_RHS_TO_LHS)
    | BOOLEAN_LANDING_ZONE_KEYS
)

# Mirrors gcp-data-ingestion/stages/enterprise/variables.tf so unfiltered
# output never emits foundation-only keys (for example finops_project_id).
INGESTION_DECLARED_VARS = frozenset({
    "core_storage_project_id",
    "core_project_id",
    "etl_compute_project_id",
    "compute_project_id",
    "primary_gold_project_id",
    "analytics_project_id",
    "bi_project_id",
    "governance_project_id",
    "bronze_dataset_id",
    "silver_dataset_id",
    "primary_gold_dataset_id",
    "gold_dataset_id",
    "quarantine_dataset_id",
    "assertions_dataset_id",
    "landing_bucket_name",
    "ops_telemetry_dataset_id",
    "dataform_repository_name",
    "dataform_release_config_name",
    "dataform_release_config_id",
    "dataform_git_commitish",
    "dataform_service_account_email",
    "dataform_sa_email",
    "batch_loader_sa_email",
    "pubsub_writer_sa_email",
    "dataplex_scan_names",
    "dataplex_profile_scan_id",
    "dataplex_quality_scan_id",
    "kms_key_id",
    "kms_key_name",
    "manage_kms_iam",
    "pii_restricted_policy_tag_id",
    "pii_masked_policy_tag_id",
    "vpc_id",
    "network_id",
    "subnet_id",
    "batch_vpc_egress",
    "artifact_registry_repository_uri",
    "batch_image_tag",
    "notification_channel_ids",
    "alert_email_addresses",
    "region",
    "environment",
    "prefix",
    "domain_name",
    "delete_contents_on_destroy",
    "enable_pubsub_stream",
    "pubsub_schema_type",
    "pubsub_target_table_id",
    "enable_batch_job",
    "batch_container_image",
    "batch_source_prefix",
    "batch_target_table",
    "batch_source_format",
    "enable_datastream_cdc",
    "datastream_source_engine",
    "datastream_db_host",
    "datastream_db_port",
    "datastream_db_username",
    "datastream_db_database",
    "datastream_db_password_secret_version",
    "datastream_cdc_mode",
    "datastream_create_private_connection",
    "datastream_network_attachment",
    "datastream_network_attachment_id",
    "datastream_peering_cidr",
    "datastream_create_without_validation",
    "enable_pipeline_workflow",
    "enable_schedule",
    "schedule_cron",
    "enable_gcs_eventarc_trigger",
    "propagation_wait_seconds",
    "labels",
    "pubsub_streams",
    "batch_jobs",
    "enable_shared_datastream_private_connection",
    "shared_datastream_private_connection_id",
    "datastream_streams",
})

# Mirrors gcp-data-science/stages/enterprise/variables.tf so --target data-science
# emits only declared Data Science stage variables.
DATA_SCIENCE_DECLARED_VARS = frozenset({
    "alert_notification_channel_ids",
    "bqml_schedule_cron",
    "core_project_id",
    "cpr_container_image",
    "cpr_model_artifact_uri",
    "cpr_model_sha256",
    "create_ml_audit_ledger_table",
    "deploy_cpr_model",
    "domain_name",
    "ds_exp_project_id",
    "ds_serving_track",
    "egress_connector_subnet_id",
    "enable_bqml_schedule",
    "enable_online_feature_store",
    "enable_scorer_service",
    "environment",
    "fairness_min_disparate_impact",
    "feature_group_source_table",
    "feature_online_store_max_nodes",
    "feature_online_store_min_nodes",
    "feature_sync_cron",
    "kms_key_id",
    "labels",
    "manage_kms_iam",
    "ml_artifact_repo_id",
    "ml_audit_dataset_id",
    "ml_audit_table_id",
    "ml_ops_project_id",
    "ml_worm_bucket_name",
    "prefix",
    "region",
    "scorer_container_image",
    "shap_additivity_tolerance",
    "silver_dataset_id",
    "vpc_id",
})


# Mirrors gcp-foundation/apps/enterprise/variables.tf so --target apps emits only
# declared Application Team Project Factory variables.
APPS_DECLARED_VARS = frozenset({
    "app_admins_group",
    "app_folder_id",
    "applications",
    "auto_unique_suffix",
    "billing_account",
    "deletion_protection",
    "enforce_vpc_sc",
    "environment",
    "environment_app_folder_ids",
    "finops_tag_value_ids",
    "kms_key_id",
    "labels",
    "manage_kms_iam",
    "manage_vpc_sc",
    "prefix",
    "project_deletion_policy",
    "project_suffix",
    "propagation_wait_seconds",
    "region",
    "shared_artifact_registry_id",
    "shared_vpc_host_project_id",
    "subnet_id",
    "vpc_id",
    "vpc_sc_perimeter_name",
})


def suggest_company_acronym(org_name: str) -> str:
    """Derive a 3-6 char lowercase company acronym from an organization name."""
    words = [w.lower() for w in re.findall(r"[A-Za-z0-9]+", org_name)]
    if not words:
        raise ValueError("Organization name must contain alphanumeric words.")
    core_indices = [i for i, w in enumerate(words) if w not in LEGAL_ENTITY_SUFFIXES]
    if len(core_indices) < 3 and len(words) >= 3:
        for i in range(len(words)):
            if i not in core_indices:
                core_indices.append(i)
                if len(core_indices) == 3:
                    break
        core_indices.sort()
    core = [words[i] for i in core_indices]
    without_group = [w for w in core if w not in OPTIONAL_GROUP_SUFFIXES]
    chosen = without_group if len(without_group) >= 3 else core
    if not chosen:
        chosen = words
    initials = "".join(w[0] for w in chosen[:6])
    if len(initials) < 3:
        for ch in chosen[0][1:]:
            if len(initials) >= 3:
                break
            initials += ch
    initials = initials[:6]
    if not initials[0].isalpha():
        initials = ("c" + initials)[:6]
    _validate_pattern("prefix", initials, PREFIX_RE)
    return initials


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate 00_linked.auto.tfvars.json for brownfield "
            "gcp-data-ingestion, gcp-data-science, or apps/enterprise deployments."
        )
    )
    parser.add_argument(
        "--target",
        choices=("ingestion", "data-science", "apps"),
        default="ingestion",
        help="Target downstream repository or stage (default: ingestion).",
    )
    parser.add_argument(
        "--context",
        type=Path,
        help="Path to platform-context.json containing existing_landing_zone values.",
    )
    parser.add_argument(
        "--env",
        dest="env",
        default=None,
        help="Target environment (dev, uat, staging, prod) for by_environment resolution.",
    )
    parser.add_argument(
        "--org-name",
        dest="org_name",
        default=None,
        help="Organization name used to suggest/populate prefix when prefix is omitted.",
    )
    for field in FIELD_FLAGS + DATA_SCIENCE_FIELD_FLAGS + APPS_FIELD_FLAGS:
        flag = "--" + field.replace("_", "-")
        parser.add_argument(flag, dest=field, default=None)
    for _, alias in ALIAS_PAIRS:
        flag = "--" + alias.replace("_", "-")
        parser.add_argument(flag, dest=alias, default=None)
    parser.add_argument(
        "--manage-kms-iam",
        dest="manage_kms_iam",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Whether Terraform manages Cloud KMS IAM bindings (defaults false when kms_key_id is set).",
    )
    parser.add_argument(
        "--export-gcs",
        dest="export_gcs",
        default=None,
        help="Optional gs://<bucket>/<path>.json URI to upload generated tfvars JSON.",
    )
    parser.add_argument(
        "--print-kms-commands",
        action="store_true",
        help="Print gcloud kms keys add-iam-policy-binding commands for customer KMS admins.",
    )
    parser.add_argument(
        "--target-variables-tf",
        type=Path,
        default=None,
        help="Optional path to target stage variables.tf to filter emitted keys.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("00_linked.auto.tfvars.json"),
        help="Output path for the generated tfvars JSON file.",
    )
    return parser.parse_args(argv)


def _validate_pattern(name: str, value: str, pattern: re.Pattern[str]) -> None:
    if not pattern.match(value):
        raise ValueError(
            f"Invalid {name} '{value}': expected format matching {pattern.pattern}"
        )


def _validate_dataform_repository(value: str) -> None:
    if not (DATAFORM_SHORT_RE.match(value) or DATAFORM_PATH_RE.match(value)):
        raise ValueError(
            f"Invalid dataform_repository_name '{value}': expected short name "
            "or projects/<project>/locations/<region>/repositories/<name>"
        )


def _validate_release_config(value: str) -> None:
    if not (DATAFORM_SHORT_RE.match(value) or RELEASE_CONFIG_PATH_RE.match(value)):
        raise ValueError(
            f"Invalid dataform_release_config_name '{value}': expected short name "
            "or projects/<project>/locations/<region>/repositories/<repo>/releaseConfigs/<name>"
        )


def _validate_dataplex_scan(name: str, value: str) -> None:
    if not (DATAPLEX_SCAN_SHORT_RE.match(value) or DATAPLEX_SCAN_PATH_RE.match(value)):
        raise ValueError(
            f"Invalid {name} '{value}': expected short scan ID "
            "or projects/<project>/locations/<region>/dataScans/<scan_id>"
        )


def _validate_environment(value: str) -> None:
    if not ENVIRONMENT_RE.match(value):
        raise ValueError(
            f"Invalid environment '{value}': expected dev, uat, staging, or prod"
        )


def _normalize_landing_zone_with_unsets(
    mapping: dict[object, object], context_label: str
) -> tuple[dict[str, object], set[str]]:
    cleaned: dict[str, object] = {}
    unset_keys: set[str] = set()
    for key, raw_val in mapping.items():
        if not isinstance(key, str) or key not in VALID_LANDING_ZONE_KEYS:
            raise ValueError(f"Unknown key in {context_label}: {key}")
        canonical = ALIAS_RHS_TO_LHS.get(key, key)
        if raw_val is None:
            unset_keys.add(canonical)
            continue
        if canonical in BOOLEAN_LANDING_ZONE_KEYS:
            if not isinstance(raw_val, bool):
                raise ValueError(
                    f"{context_label}.{key} must be a boolean, got {type(raw_val).__name__}"
                )
            cleaned[key] = raw_val
            continue
        if not isinstance(raw_val, str):
            raise ValueError(
                f"{context_label}.{key} must be a string, got {type(raw_val).__name__}"
            )
        stripped = raw_val.strip()
        if stripped:
            cleaned[key] = stripped
        else:
            unset_keys.add(canonical)

    for primary, alias in ALIAS_PAIRS:
        if primary in cleaned and alias in cleaned and cleaned[primary] != cleaned[alias]:
            raise ValueError(
                f"Conflicting values for {primary} and alias {alias} in {context_label}"
            )

    normalized: dict[str, object] = {}
    for key, val in cleaned.items():
        canonical = ALIAS_RHS_TO_LHS.get(key, key)
        unset_keys.discard(canonical)
        if canonical not in normalized:
            normalized[canonical] = val
    return normalized, unset_keys


def _normalize_landing_zone_dict(
    mapping: dict[object, object], context_label: str
) -> dict[str, object]:
    normalized, _ = _normalize_landing_zone_with_unsets(mapping, context_label)
    return normalized


def _validate_ml_artifact_repo(value: str) -> None:
    if not (
        ML_ARTIFACT_REPO_SHORT_RE.match(value)
        or ML_ARTIFACT_REPO_PATH_RE.match(value)
        or ARTIFACT_REGISTRY_URI_RE.match(value)
    ):
        raise ValueError(
            f"Invalid ml_artifact_repo_id '{value}': expected short repo ID, "
            "projects/<project>/locations/<region>/repositories/<repo>, "
            "or <region>-docker.pkg.dev/<project>/<repo>"
        )


def validate_data_science_config(payload: dict[str, object]) -> dict[str, object]:
    ds_cfg = payload.get("data_science")
    if not isinstance(ds_cfg, dict):
        raise ValueError("data_science must be a JSON object.")
    if set(ds_cfg.keys()) != DATA_SCIENCE_CONFIG_KEYS:
        missing = sorted(DATA_SCIENCE_CONFIG_KEYS - set(ds_cfg.keys()))
        extra = sorted(set(ds_cfg.keys()) - DATA_SCIENCE_CONFIG_KEYS)
        raise ValueError(
            f"Invalid data_science keys (missing={missing}, extra={extra})."
        )
    for bool_key in (
        "enable_data_science",
        "enable_ds_workbench",
        "enable_colab_enterprise",
        "enable_online_feature_store",
    ):
        if not isinstance(ds_cfg[bool_key], bool):
            raise ValueError(
                f"data_science.{bool_key} must be a boolean, got {type(ds_cfg[bool_key]).__name__}"
            )
    track = ds_cfg["ds_serving_track"]
    if not isinstance(track, str) or track not in DS_SERVING_TRACKS:
        raise ValueError(
            f"Invalid data_science.ds_serving_track '{track}': expected one of {sorted(DS_SERVING_TRACKS)}"
        )
    retention = ds_cfg["xai_audit_retention_days"]
    if isinstance(retention, bool) or not isinstance(retention, int) or retention <= 0:
        raise ValueError("data_science.xai_audit_retention_days must be a positive integer.")
    shap_tol = ds_cfg["shap_additivity_tolerance"]
    if (
        isinstance(shap_tol, bool)
        or not isinstance(shap_tol, (int, float))
        or shap_tol <= 0
        or shap_tol > 0.001
    ):
        raise ValueError("data_science.shap_additivity_tolerance must be > 0 and <= 0.001.")
    disparate = ds_cfg["fairness_min_disparate_impact"]
    if (
        isinstance(disparate, bool)
        or not isinstance(disparate, (int, float))
        or disparate <= 0.0
        or disparate > 1.0
    ):
        raise ValueError("data_science.fairness_min_disparate_impact must be > 0.0 and <= 1.0.")

    compliance = payload.get("compliance_profile")
    if compliance == "regulated_fsi_rmit":
        if ds_cfg["enable_colab_enterprise"]:
            raise ValueError(
                "data_science.enable_colab_enterprise cannot be true when compliance_profile is regulated_fsi_rmit."
            )
        if retention < 2555:
            raise ValueError(
                "data_science.xai_audit_retention_days must be >= 2555 when compliance_profile is regulated_fsi_rmit."
            )

    primary_region = payload.get("primary_region")
    if primary_region == "asia-southeast2" and ds_cfg["enable_online_feature_store"]:
        raise ValueError(
            "data_science.enable_online_feature_store cannot be true when primary_region is asia-southeast2."
        )
    return ds_cfg


def validate_finops_config(payload: dict[str, object]) -> dict[str, object]:
    finops_cfg = payload.get("finops")
    if not isinstance(finops_cfg, dict):
        raise ValueError("finops must be a JSON object.")
    dept_budgets = finops_cfg.get("department_budgets")
    if dept_budgets is not None:
        if not isinstance(dept_budgets, dict) or not dept_budgets:
            raise ValueError("finops.department_budgets must be a non-empty JSON object.")
        for dept, amt in dept_budgets.items():
            if not isinstance(dept, str) or not dept.strip():
                raise ValueError("finops.department_budgets keys must be non-empty strings.")
            if isinstance(amt, bool) or not isinstance(amt, (int, float)) or amt <= 0:
                raise ValueError(
                    f"finops.department_budgets.{dept} must be a positive number."
                )
    return finops_cfg


def validate_scc_config(payload: dict[str, object]) -> dict[str, object]:
    scc_cfg = payload.get("scc")
    if not isinstance(scc_cfg, dict):
        raise ValueError("scc must be a JSON object.")
    scc_scope = scc_cfg.get("scc_scope")
    if scc_scope is not None and scc_scope not in ("ORGANIZATION", "FOLDER", "PROJECT"):
        raise ValueError(
            "scc.scc_scope must be one of ORGANIZATION, FOLDER, or PROJECT."
        )
    dedicated = scc_cfg.get("create_dedicated_secops_project")
    if dedicated is not None and not isinstance(dedicated, bool):
        raise ValueError(
            f"scc.create_dedicated_secops_project must be a boolean, got {type(dedicated).__name__}"
        )
    return scc_cfg


def validate_enterprise_teams_config(payload: dict[str, object]) -> dict[str, object]:
    teams_cfg = payload.get("enterprise_teams")
    if not isinstance(teams_cfg, dict):
        raise ValueError("enterprise_teams must be a JSON object.")
    if set(teams_cfg.keys()) != ENTERPRISE_TEAMS_KEYS:
        missing = sorted(ENTERPRISE_TEAMS_KEYS - set(teams_cfg.keys()))
        extra = sorted(set(teams_cfg.keys()) - ENTERPRISE_TEAMS_KEYS)
        raise ValueError(
            f"Invalid enterprise_teams keys (missing={missing}, extra={extra})."
        )
    for key, val in teams_cfg.items():
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"enterprise_teams.{key} must be a non-empty group email string.")
        _validate_pattern(f"enterprise_teams.{key}", val.strip(), SA_EMAIL_RE)
    return teams_cfg


def validate_applications_config(payload: dict[str, object]) -> dict[str, object]:
    apps_cfg = payload.get("applications")
    if not isinstance(apps_cfg, dict):
        raise ValueError("applications must be a JSON object.")
    if set(apps_cfg.keys()) != APPLICATIONS_KEYS:
        missing = sorted(APPLICATIONS_KEYS - set(apps_cfg.keys()))
        extra = sorted(set(apps_cfg.keys()) - APPLICATIONS_KEYS)
        raise ValueError(
            f"Invalid applications keys (missing={missing}, extra={extra})."
        )
    for bool_key in ("enable_apps", "shared_artifact_registry"):
        if not isinstance(apps_cfg[bool_key], bool):
            raise ValueError(
                f"applications.{bool_key} must be a boolean, got {type(apps_cfg[bool_key]).__name__}"
            )
    workloads = apps_cfg["workloads"]
    if not isinstance(workloads, dict):
        raise ValueError("applications.workloads must be a JSON object.")
    for app_key, wl in workloads.items():
        if not isinstance(app_key, str) or not app_key.strip():
            raise ValueError("applications.workloads keys must be non-empty strings.")
        if not isinstance(wl, dict):
            raise ValueError(f"applications.workloads.{app_key} must be a JSON object.")
        if set(wl.keys()) != APPLICATION_WORKLOAD_KEYS:
            missing = sorted(APPLICATION_WORKLOAD_KEYS - set(wl.keys()))
            extra = sorted(set(wl.keys()) - APPLICATION_WORKLOAD_KEYS)
            raise ValueError(
                f"Invalid applications.workloads.{app_key} keys (missing={missing}, extra={extra})."
            )
        if not isinstance(wl["display_name"], str) or not wl["display_name"].strip():
            raise ValueError(f"applications.workloads.{app_key}.display_name must be a non-empty string.")
        for wl_bool in ("enable_cloud_run", "enable_gke", "enable_cloud_sql"):
            if not isinstance(wl[wl_bool], bool):
                raise ValueError(
                    f"applications.workloads.{app_key}.{wl_bool} must be a boolean."
                )
        for grp_key in ("admin_group", "developer_group"):
            grp_val = wl[grp_key]
            if not isinstance(grp_val, str) or not grp_val.strip():
                raise ValueError(
                    f"applications.workloads.{app_key}.{grp_key} must be a non-empty group email."
                )
            _validate_pattern(
                f"applications.workloads.{app_key}.{grp_key}",
                grp_val.strip(),
                SA_EMAIL_RE,
            )
    return apps_cfg


def load_context_values(
    context_path: Path, target_env: str | None = None
) -> dict[str, object]:
    if not context_path.is_file():
        raise FileNotFoundError(f"Context file not found: {context_path}")
    payload = json.loads(context_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("platform-context.json must contain a JSON object.")

    if target_env is not None:
        _validate_environment(target_env)

    values: dict[str, object] = {}
    if "finops" in payload and payload["finops"] is not None:
        validate_finops_config(payload)
    if "scc" in payload and payload["scc"] is not None:
        validate_scc_config(payload)
    if "enterprise_teams" in payload and payload["enterprise_teams"] is not None:
        teams_cfg = validate_enterprise_teams_config(payload)
        values["app_admins_group"] = str(teams_cfg["app_admins_group"]).strip()
    if "applications" in payload and payload["applications"] is not None:
        apps_cfg = validate_applications_config(payload)
        if apps_cfg["enable_apps"]:
            values["applications"] = apps_cfg["workloads"]
    if "data_science" in payload and payload["data_science"] is not None:
        ds_cfg = validate_data_science_config(payload)
        for ds_key in (
            "ds_serving_track",
            "enable_online_feature_store",
            "shap_additivity_tolerance",
            "fairness_min_disparate_impact",
        ):
            values[ds_key] = ds_cfg[ds_key]

    landing_zone = payload.get("existing_landing_zone")
    if landing_zone is not None:
        if not isinstance(landing_zone, dict):
            raise ValueError("existing_landing_zone must be a JSON object.")

        base_raw = {k: v for k, v in landing_zone.items() if k != "by_environment"}
        values.update(_normalize_landing_zone_dict(base_raw, "existing_landing_zone"))

        if "by_environment" in landing_zone:
            by_env = landing_zone["by_environment"]
            if not isinstance(by_env, dict) or not by_env:
                raise ValueError(
                    "existing_landing_zone.by_environment must be a non-empty JSON object."
                )

            normalized_by_env: dict[str, tuple[dict[str, object], set[str]]] = {}
            for env_key, env_obj in by_env.items():
                if not isinstance(env_key, str) or not ENVIRONMENT_RE.match(env_key):
                    raise ValueError(
                        f"Invalid environment key '{env_key}' in existing_landing_zone.by_environment"
                    )
                if not isinstance(env_obj, dict):
                    raise ValueError(
                        f"existing_landing_zone.by_environment.{env_key} must be a JSON object."
                    )
                normalized_by_env[env_key] = _normalize_landing_zone_with_unsets(
                    env_obj, f"existing_landing_zone.by_environment.{env_key}"
                )

            selected_env = target_env
            if selected_env is None:
                selected_env = values.get("environment")
            if selected_env is None:
                envs = payload.get("environments")
                if (
                    isinstance(envs, list)
                    and envs
                    and isinstance(envs[0], str)
                    and envs[0].strip()
                ):
                    selected_env = envs[0].strip()

            if not selected_env or selected_env not in normalized_by_env:
                raise ValueError(
                    f"Environment '{selected_env}' not found in existing_landing_zone.by_environment"
                )

            env_values, unset_keys = normalized_by_env[selected_env]
            for unset_key in unset_keys:
                values.pop(unset_key, None)
            values.update(env_values)
            values["environment"] = selected_env
        elif target_env is not None:
            values["environment"] = target_env

    top_level_mappings = (
        ("primary_region", "region"),
        ("prefix", "prefix"),
        ("project_suffix", "project_suffix"),
    )
    for src_key, dst_key in top_level_mappings:
        raw_val = payload.get(src_key)
        if dst_key not in values and isinstance(raw_val, str) and raw_val.strip():
            values[dst_key] = raw_val.strip()

    if "environment" not in values:
        if target_env is not None:
            values["environment"] = target_env
        else:
            envs = payload.get("environments")
            if isinstance(envs, list) and envs and isinstance(envs[0], str) and envs[0].strip():
                values["environment"] = envs[0].strip()

    return values


def validate_inputs(values: dict[str, object], target: str = "ingestion") -> None:
    if target == "data-science":
        required_fields = DATA_SCIENCE_REQUIRED_FIELDS
    elif target == "apps":
        required_fields = APPS_REQUIRED_FIELDS
    else:
        required_fields = REQUIRED_FIELDS
    for required in required_fields:
        if not values.get(required):
            raise ValueError(f"Missing required brownfield field: {required}")

    for field in (
        "core_project_id",
        "compute_project_id",
        "analytics_project_id",
        "bi_project_id",
        "governance_project_id",
        "finops_project_id",
        "backup_project_id",
        "ds_exp_project_id",
        "ml_ops_project_id",
        "shared_vpc_host_project_id",
    ):
        val = values.get(field)
        if isinstance(val, str) and val:
            _validate_pattern(field, val, PROJECT_ID_RE)

    for field in (
        "bronze_dataset_id",
        "silver_dataset_id",
        "gold_dataset_id",
        "quarantine_dataset_id",
        "assertions_dataset_id",
        "ops_telemetry_dataset_id",
        "ml_audit_dataset_id",
    ):
        val = values.get(field)
        if isinstance(val, str) and val:
            _validate_pattern(field, val, DATASET_ID_RE)

    if values.get("ml_audit_table_id"):
        _validate_pattern(
            "ml_audit_table_id", str(values["ml_audit_table_id"]), TABLE_ID_RE
        )

    if values.get("landing_bucket_name"):
        _validate_pattern(
            "landing_bucket_name", str(values["landing_bucket_name"]), BUCKET_NAME_RE
        )
    if values.get("ml_worm_bucket_name"):
        _validate_pattern(
            "ml_worm_bucket_name", str(values["ml_worm_bucket_name"]), BUCKET_NAME_RE
        )
    if values.get("dataform_repository_name"):
        _validate_dataform_repository(str(values["dataform_repository_name"]))
    if values.get("ml_artifact_repo_id"):
        _validate_ml_artifact_repo(str(values["ml_artifact_repo_id"]))

    if values.get("dataform_release_config_name"):
        _validate_release_config(str(values["dataform_release_config_name"]))

    for scan_field in ("dataplex_profile_scan_id", "dataplex_quality_scan_id"):
        val = values.get(scan_field)
        if isinstance(val, str) and val:
            _validate_dataplex_scan(scan_field, val)

    for field in (
        "dataform_sa_email",
        "batch_loader_sa_email",
        "pubsub_writer_sa_email",
    ):
        val = values.get(field)
        if isinstance(val, str) and val:
            _validate_pattern(field, val, SA_EMAIL_RE)

    if values.get("kms_key_id"):
        _validate_pattern("kms_key_id", str(values["kms_key_id"]), KMS_KEY_RE)
    if values.get("backup_vault_id"):
        _validate_pattern(
            "backup_vault_id", str(values["backup_vault_id"]), BACKUP_VAULT_ID_RE
        )
    if values.get("vpc_id"):
        _validate_pattern("vpc_id", str(values["vpc_id"]), VPC_ID_RE)
    if values.get("subnet_id"):
        _validate_pattern("subnet_id", str(values["subnet_id"]), SUBNET_ID_RE)
    if values.get("egress_connector_subnet_id"):
        _validate_pattern(
            "egress_connector_subnet_id",
            str(values["egress_connector_subnet_id"]),
            SUBNET_ID_RE,
        )
    if values.get("datastream_network_attachment_id"):
        _validate_pattern(
            "datastream_network_attachment_id",
            str(values["datastream_network_attachment_id"]),
            NETWORK_ATTACHMENT_RE,
        )
    if values.get("pii_restricted_policy_tag_id"):
        _validate_pattern(
            "pii_restricted_policy_tag_id",
            str(values["pii_restricted_policy_tag_id"]),
            POLICY_TAG_RE,
        )
    if values.get("pii_masked_policy_tag_id"):
        _validate_pattern(
            "pii_masked_policy_tag_id",
            str(values["pii_masked_policy_tag_id"]),
            POLICY_TAG_RE,
        )
    if values.get("artifact_registry_repository_uri"):
        _validate_pattern(
            "artifact_registry_repository_uri",
            str(values["artifact_registry_repository_uri"]),
            ARTIFACT_REGISTRY_URI_RE,
        )
    if values.get("region"):
        _validate_pattern("region", str(values["region"]), REGION_RE)
    if values.get("environment"):
        _validate_pattern("environment", str(values["environment"]), ENVIRONMENT_RE)
    if values.get("prefix"):
        _validate_pattern("prefix", str(values["prefix"]), PREFIX_RE)
    if values.get("project_suffix"):
        _validate_pattern("project_suffix", str(values["project_suffix"]), PROJECT_SUFFIX_RE)
    if values.get("billing_account"):
        _validate_pattern("billing_account", str(values["billing_account"]), BILLING_ACCOUNT_RE)
    if values.get("app_folder_id"):
        _validate_pattern("app_folder_id", str(values["app_folder_id"]), FOLDER_ID_RE)
    if values.get("shared_artifact_registry_id"):
        _validate_ml_artifact_repo(str(values["shared_artifact_registry_id"]))
    if values.get("app_admins_group"):
        _validate_pattern("app_admins_group", str(values["app_admins_group"]), SA_EMAIL_RE)
    if values.get("project_deletion_policy"):
        pol = str(values["project_deletion_policy"])
        if pol not in PROJECT_DELETION_POLICIES:
            raise ValueError(
                f"Invalid project_deletion_policy '{pol}': expected one of {sorted(PROJECT_DELETION_POLICIES)}"
            )
    if values.get("domain_name"):
        _validate_pattern("domain_name", str(values["domain_name"]), DOMAIN_NAME_RE)
    if values.get("ds_serving_track"):
        track = str(values["ds_serving_track"])
        if track not in DS_SERVING_TRACKS:
            raise ValueError(
                f"Invalid ds_serving_track '{track}': expected one of {sorted(DS_SERVING_TRACKS)}"
            )
    if (
        values.get("region") == "asia-southeast2"
        and values.get("enable_online_feature_store") is True
    ):
        raise ValueError(
            "enable_online_feature_store cannot be true when region is asia-southeast2."
        )


def resolve_env_gcs_uri(uri: str, env: str) -> str:
    if not env:
        return uri
    rest = uri[len("gs://"):]
    if "/" not in rest:
        return f"gs://{rest}/{env}/foundation-outputs.json"
    bucket, obj = rest.split("/", 1)
    obj = obj.lstrip("/")
    if not obj:
        return f"gs://{bucket}/{env}/foundation-outputs.json"
    if obj == "shared" or obj.startswith("shared/"):
        return uri
    parts = obj.split("/")
    filename = parts[-1]
    if env in parts[:-1]:
        return uri
    if filename and (
        f"-{env}." in filename
        or filename.startswith(f"{env}-")
        or filename == f"{env}.json"
    ):
        return uri
    if obj.endswith("/"):
        return f"gs://{bucket}/{obj}{env}/foundation-outputs.json"
    parent = "/".join(parts[:-1])
    if parent:
        return f"gs://{bucket}/{parent}/{env}/{filename}"
    return f"gs://{bucket}/{env}/{filename}"


def format_kms_binding_commands(
    values: dict[str, object], target: str = "ingestion"
) -> list[str]:
    kms_key_id = values.get("kms_key_id")
    if not isinstance(kms_key_id, str) or not kms_key_id:
        raise ValueError("kms_key_id is required when --print-kms-commands is passed.")
    match = KMS_KEY_RE.match(kms_key_id)
    if not match:
        raise ValueError(f"Invalid kms_key_id '{kms_key_id}'")
    kms_project, kms_location, kms_keyring, kms_key = match.groups()

    if target == "data-science":
        ml_ops_project = values.get("ml_ops_project_id")
        if not isinstance(ml_ops_project, str) or not ml_ops_project:
            raise ValueError("ml_ops_project_id is required when --print-kms-commands is passed.")
        ds_exp_project = values.get("ds_exp_project_id")
        if not isinstance(ds_exp_project, str) or not ds_exp_project:
            raise ValueError("ds_exp_project_id is required when --print-kms-commands is passed.")

        commands = [
            f"ML_OPS_PROJECT_NUMBER=\"$(gcloud projects describe '{ml_ops_project}' --format='value(projectNumber)')\"",
            f"DS_EXP_PROJECT_NUMBER=\"$(gcloud projects describe '{ds_exp_project}' --format='value(projectNumber)')\"",
        ]
        members = [
            "serviceAccount:service-${ML_OPS_PROJECT_NUMBER}@gcp-sa-aiplatform.iam.gserviceaccount.com",
            "serviceAccount:service-${ML_OPS_PROJECT_NUMBER}@gcp-sa-artifactregistry.iam.gserviceaccount.com",
            "serviceAccount:service-${ML_OPS_PROJECT_NUMBER}@gs-project-accounts.iam.gserviceaccount.com",
            "serviceAccount:bq-${ML_OPS_PROJECT_NUMBER}@bigquery-encryption.iam.gserviceaccount.com",
            "serviceAccount:service-${ML_OPS_PROJECT_NUMBER}@gcp-sa-dataplex.iam.gserviceaccount.com",
            "serviceAccount:service-${ML_OPS_PROJECT_NUMBER}@serverless-robot-prod.iam.gserviceaccount.com",
            "serviceAccount:service-${ML_OPS_PROJECT_NUMBER}@gcp-sa-workflows.iam.gserviceaccount.com",
            "serviceAccount:service-${ML_OPS_PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com",
            "serviceAccount:service-${DS_EXP_PROJECT_NUMBER}@gcp-sa-notebooks.iam.gserviceaccount.com",
            "serviceAccount:service-${DS_EXP_PROJECT_NUMBER}@compute-system.iam.gserviceaccount.com",
        ]
        commands.extend(
            (
                f"gcloud kms keys add-iam-policy-binding {kms_key} "
                f"--project={kms_project} --location={kms_location} --keyring={kms_keyring} "
                f"--member={member} --role=roles/cloudkms.cryptoKeyEncrypterDecrypter"
            )
            for member in members
        )
        return commands

    if target == "apps":
        prefix = str(values.get("prefix") or "ent")
        env_name = str(values.get("environment") or "dev")
        commands = [
            f"# CMEK preflight/remediation for apps/enterprise ({prefix}-{env_name}) on {kms_key_id}:",
            "APP_PROJECT_NUMBER=\"$(gcloud projects describe '<APP_PROJECT_ID>' --format='value(projectNumber)')\"",
        ]
        members = [
            "serviceAccount:service-${APP_PROJECT_NUMBER}@serverless-robot-prod.iam.gserviceaccount.com",
            "serviceAccount:service-${APP_PROJECT_NUMBER}@container-engine-robot.iam.gserviceaccount.com",
            "serviceAccount:service-${APP_PROJECT_NUMBER}@gcp-sa-cloud-sql.iam.gserviceaccount.com",
            "serviceAccount:service-${APP_PROJECT_NUMBER}@gcp-sa-artifactregistry.iam.gserviceaccount.com",
            "serviceAccount:service-${APP_PROJECT_NUMBER}@compute-system.iam.gserviceaccount.com",
        ]
        commands.extend(
            (
                f"gcloud kms keys add-iam-policy-binding {kms_key} "
                f"--project={kms_project} --location={kms_location} --keyring={kms_keyring} "
                f"--member={member} --role=roles/cloudkms.cryptoKeyEncrypterDecrypter"
            )
            for member in members
        )
        return commands

    compute_project = values.get("compute_project_id")
    if not isinstance(compute_project, str) or not compute_project:
        raise ValueError("compute_project_id is required when --print-kms-commands is passed.")

    batch_sa = values.get("batch_loader_sa_email")
    if not isinstance(batch_sa, str) or not batch_sa:
        prefix = values.get("prefix") if isinstance(values.get("prefix"), str) and values.get("prefix") else "ent"
        batch_sa = f"{prefix}-batch-loader@{compute_project}.iam.gserviceaccount.com"

    commands = [
        f"COMPUTE_PROJECT_NUMBER=\"$(gcloud projects describe '{compute_project}' --format='value(projectNumber)')\""
    ]
    members = [
        "serviceAccount:service-${COMPUTE_PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com",
        "serviceAccount:service-${COMPUTE_PROJECT_NUMBER}@gcp-sa-datastream.iam.gserviceaccount.com",
        "serviceAccount:service-${COMPUTE_PROJECT_NUMBER}@gcp-sa-workflows.iam.gserviceaccount.com",
        "serviceAccount:service-${COMPUTE_PROJECT_NUMBER}@serverless-robot-prod.iam.gserviceaccount.com",
        f"serviceAccount:{batch_sa}",
    ]
    commands.extend(
        (
            f"gcloud kms keys add-iam-policy-binding {kms_key} "
            f"--project={kms_project} --location={kms_location} --keyring={kms_keyring} "
            f"--member={member} --role=roles/cloudkms.cryptoKeyEncrypterDecrypter"
        )
        for member in members
    )
    return commands


def format_shared_vpc_commands(
    values: dict[str, object], target: str = "ingestion"
) -> list[str]:
    if target == "apps":
        subnet_id = values.get("subnet_id")
        if not isinstance(subnet_id, str) or not subnet_id:
            return []
        match = SUBNET_ID_RE.match(subnet_id)
        if not match:
            return []
        host_project, region, subnet_name = match.groups()
        explicit_host = values.get("shared_vpc_host_project_id")
        if isinstance(explicit_host, str) and explicit_host:
            host_project = explicit_host
        return [
            f"# Shared VPC preflight/remediation for apps/enterprise on subnet {subnet_name} (host {host_project}):",
            "APP_PROJECT_NUMBER=\"$(gcloud projects describe '<APP_PROJECT_ID>' --format='value(projectNumber)')\"",
            f"gcloud compute shared-vpc associated-projects add '<APP_PROJECT_ID>' --host-project='{host_project}'",
            (
                f"gcloud compute networks subnets add-iam-policy-binding '{subnet_name}' "
                f"--project='{host_project}' --region='{region}' "
                "--member=\"serviceAccount:service-${APP_PROJECT_NUMBER}@serverless-robot-prod.iam.gserviceaccount.com\" "
                "--role=roles/compute.networkUser"
            ),
            (
                f"gcloud compute networks subnets add-iam-policy-binding '{subnet_name}' "
                f"--project='{host_project}' --region='{region}' "
                "--member=\"serviceAccount:${APP_PROJECT_NUMBER}@cloudservices.gserviceaccount.com\" "
                "--role=roles/compute.networkUser"
            ),
            (
                f"gcloud compute networks subnets add-iam-policy-binding '{subnet_name}' "
                f"--project='{host_project}' --region='{region}' "
                "--member=\"serviceAccount:service-${APP_PROJECT_NUMBER}@container-engine-robot.iam.gserviceaccount.com\" "
                "--role=roles/compute.networkUser"
            ),
            (
                f"gcloud projects add-iam-policy-binding '{host_project}' "
                "--member=\"serviceAccount:service-${APP_PROJECT_NUMBER}@container-engine-robot.iam.gserviceaccount.com\" "
                "--role=roles/container.hostServiceAgentUser"
            ),
        ]
    if target != "data-science":
        return []
    subnet_id = values.get("egress_connector_subnet_id")
    ml_ops_project = values.get("ml_ops_project_id")
    if not isinstance(subnet_id, str) or not subnet_id:
        return []
    if not isinstance(ml_ops_project, str) or not ml_ops_project:
        return []
    match = SUBNET_ID_RE.match(subnet_id)
    if not match:
        return []
    host_project, region, subnet_name = match.groups()
    if host_project == ml_ops_project:
        return []
    return [
        f"# Shared VPC preflight/remediation for ml_ops ({ml_ops_project}) on egress_connector_subnet_id:",
        f"ML_OPS_PROJECT_NUMBER=\"$(gcloud projects describe '{ml_ops_project}' --format='value(projectNumber)')\"",
        f"gcloud compute shared-vpc associated-projects add '{ml_ops_project}' --host-project='{host_project}'",
        (
            f"gcloud compute networks subnets add-iam-policy-binding '{subnet_name}' "
            f"--project='{host_project}' --region='{region}' "
            "--member=\"serviceAccount:service-${ML_OPS_PROJECT_NUMBER}@serverless-robot-prod.iam.gserviceaccount.com\" "
            "--role=roles/compute.networkUser"
        ),
    ]


def build_linked_tfvars(
    values: dict[str, object],
    target_variables_tf: Path | None = None,
    target: str = "ingestion",
) -> dict[str, object]:
    linked: dict[str, object] = {}
    for key, val in values.items():
        if isinstance(val, bool) or val:
            linked[key] = val

    for primary, alias in ALIAS_PAIRS:
        if primary in linked and alias not in linked:
            linked[alias] = linked[primary]

    if target_variables_tf is not None:
        if not target_variables_tf.is_file():
            raise FileNotFoundError(
                f"Target variables.tf not found: {target_variables_tf}"
            )
        declared = set(
            TF_VAR_DECL_RE.findall(target_variables_tf.read_text(encoding="utf-8"))
        )
    elif target == "data-science":
        declared = DATA_SCIENCE_DECLARED_VARS
    elif target == "apps":
        declared = APPS_DECLARED_VARS
    else:
        declared = INGESTION_DECLARED_VARS

    if target == "data-science" and "create_ml_audit_ledger_table" not in linked:
        linked["create_ml_audit_ledger_table"] = True

    if target == "apps" and "shared_vpc_host_project_id" not in linked:
        subnet_val = linked.get("subnet_id")
        if isinstance(subnet_val, str):
            sub_match = SUBNET_ID_RE.match(subnet_val)
            if sub_match:
                linked["shared_vpc_host_project_id"] = sub_match.group(1)

    linked = {k: v for k, v in linked.items() if k in declared}
    return dict(sorted(linked.items()))


def write_atomic_json(output_path: Path, payload: dict[str, object]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        dir=str(output_path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, output_path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def _resolve_cli_environment(raw_env: str | None, raw_environment: str | None) -> str | None:
    cleaned_env: str | None = None
    cleaned_environment: str | None = None
    if raw_env is not None:
        cleaned_env = raw_env.strip()
        _validate_environment(cleaned_env)
    if raw_environment is not None:
        cleaned_environment = raw_environment.strip()
        _validate_environment(cleaned_environment)
    if (
        cleaned_env is not None
        and cleaned_environment is not None
        and cleaned_env != cleaned_environment
    ):
        raise ValueError("Conflicting --env and --environment values.")
    return cleaned_env if cleaned_env is not None else cleaned_environment


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.export_gcs is not None:
        cleaned_gcs = args.export_gcs.strip()
        if not cleaned_gcs or not GCS_URI_RE.match(cleaned_gcs):
            print(f"ERROR: Invalid --export-gcs URI '{args.export_gcs}'", file=sys.stderr)
            return 2

    try:
        target_env = _resolve_cli_environment(args.env, args.environment)

        for primary, alias in ALIAS_PAIRS:
            raw_primary = getattr(args, primary, None)
            raw_alias = getattr(args, alias, None)
            if raw_primary is not None and raw_alias is not None:
                if raw_primary.strip() != raw_alias.strip():
                    raise ValueError(
                        f"Conflicting CLI flags for {primary} and alias {alias}."
                    )

        values: dict[str, object] = {}
        if args.context is not None:
            values.update(load_context_values(args.context, target_env=target_env))
        elif target_env is not None:
            values["environment"] = target_env

        for field in FIELD_FLAGS + DATA_SCIENCE_FIELD_FLAGS + APPS_FIELD_FLAGS:
            if field == "environment":
                continue
            cli_val = getattr(args, field, None)
            if cli_val is not None:
                cleaned = cli_val.strip()
                if cleaned:
                    values[field] = cleaned
                else:
                    values.pop(field, None)

        if args.org_name is not None and not values.get("prefix"):
            suggested_prefix = suggest_company_acronym(args.org_name)
            values["prefix"] = suggested_prefix
            print(
                f"Suggested prefix '{suggested_prefix}' from organization name '{args.org_name}'."
            )

        for primary, alias in ALIAS_PAIRS:
            cli_val = getattr(args, alias, None)
            if cli_val is not None:
                cleaned = cli_val.strip()
                if cleaned:
                    values[primary] = cleaned
                else:
                    values.pop(primary, None)

        if args.manage_kms_iam is not None:
            values["manage_kms_iam"] = args.manage_kms_iam
        elif values.get("kms_key_id") and values.get("manage_kms_iam") is not True:
            values["manage_kms_iam"] = False

        validate_inputs(values, target=args.target)
        linked = build_linked_tfvars(
            values, args.target_variables_tf, target=args.target
        )
        write_atomic_json(args.output, linked)

        if args.export_gcs is not None:
            env_str = str(values.get("environment") or "")
            resolved_gcs_uri = resolve_env_gcs_uri(args.export_gcs.strip(), env_str)
            if not re.match(r"^gs://[^/]+/.+", resolved_gcs_uri):
                raise ValueError(f"Invalid GCS URI (missing object path): {resolved_gcs_uri}")
            if shutil.which("gcloud"):
                subprocess.run(
                    ["gcloud", "storage", "cp", str(args.output), resolved_gcs_uri],
                    check=True,
                )
            elif shutil.which("gsutil"):
                subprocess.run(
                    ["gsutil", "cp", str(args.output), resolved_gcs_uri],
                    check=True,
                )
            else:
                raise OSError("Neither gcloud nor gsutil is installed in PATH.")
            print(f"Uploaded linked variables to {resolved_gcs_uri}")

        if args.print_kms_commands:
            for cmd in format_kms_binding_commands(values, target=args.target):
                print(cmd)
        for cmd in format_shared_vpc_commands(values, target=args.target):
            print(cmd)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {len(linked)} linked variable(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
