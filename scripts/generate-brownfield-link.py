#!/usr/bin/env python3
"""Generate 00_linked.auto.tfvars.json for brownfield gcp-data-ingestion deployments."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile

PROJECT_ID_RE = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
DATASET_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
BUCKET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$")
ENVIRONMENT_RE = re.compile(r"^(dev|staging|prod)$")
PREFIX_RE = re.compile(r"^[a-z][a-z0-9-]{1,6}[a-z0-9]$")
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
    r"^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/locations/[a-z0-9-]+/keyRings/[A-Za-z0-9._-]+/cryptoKeys/[A-Za-z0-9._-]+$"
)
VPC_ID_RE = re.compile(
    r"^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/global/networks/[A-Za-z0-9._-]+$"
)
SUBNET_ID_RE = re.compile(
    r"^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/regions/[a-z0-9-]+/subnetworks/[A-Za-z0-9._-]+$"
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
TF_VAR_DECL_RE = re.compile(r'^\s*variable\s+"([A-Za-z0-9_]+)"\s*\{', re.MULTILINE)

REQUIRED_FIELDS = (
    "core_project_id",
    "compute_project_id",
    "bronze_dataset_id",
    "landing_bucket_name",
    "dataform_repository_name",
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
)

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
VALID_LANDING_ZONE_KEYS = frozenset(FIELD_FLAGS) | frozenset(ALIAS_RHS_TO_LHS)

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


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate 00_linked.auto.tfvars.json for brownfield "
            "gcp-data-ingestion deployments."
        )
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
        help="Target environment (dev, staging, prod) for by_environment resolution.",
    )
    for field in FIELD_FLAGS:
        flag = "--" + field.replace("_", "-")
        parser.add_argument(flag, dest=field, default=None)
    for _, alias in ALIAS_PAIRS:
        flag = "--" + alias.replace("_", "-")
        parser.add_argument(flag, dest=alias, default=None)
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
            f"Invalid environment '{value}': expected dev, staging, or prod"
        )


def _normalize_landing_zone_with_unsets(
    mapping: dict[object, object], context_label: str
) -> tuple[dict[str, str], set[str]]:
    cleaned: dict[str, str] = {}
    unset_keys: set[str] = set()
    for key, raw_val in mapping.items():
        if not isinstance(key, str) or key not in VALID_LANDING_ZONE_KEYS:
            raise ValueError(f"Unknown key in {context_label}: {key}")
        canonical = ALIAS_RHS_TO_LHS.get(key, key)
        if raw_val is None:
            unset_keys.add(canonical)
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

    normalized: dict[str, str] = {}
    for key, val in cleaned.items():
        canonical = ALIAS_RHS_TO_LHS.get(key, key)
        unset_keys.discard(canonical)
        if canonical not in normalized:
            normalized[canonical] = val
    return normalized, unset_keys


def _normalize_landing_zone_dict(
    mapping: dict[object, object], context_label: str
) -> dict[str, str]:
    normalized, _ = _normalize_landing_zone_with_unsets(mapping, context_label)
    return normalized


def load_context_values(
    context_path: Path, target_env: str | None = None
) -> dict[str, str]:
    if not context_path.is_file():
        raise FileNotFoundError(f"Context file not found: {context_path}")
    payload = json.loads(context_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("platform-context.json must contain a JSON object.")

    if target_env is not None:
        _validate_environment(target_env)

    values: dict[str, str] = {}
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

            normalized_by_env: dict[str, tuple[dict[str, str], set[str]]] = {}
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


def validate_inputs(values: dict[str, str]) -> None:
    for required in REQUIRED_FIELDS:
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
    ):
        if values.get(field):
            _validate_pattern(field, values[field], PROJECT_ID_RE)

    for field in (
        "bronze_dataset_id",
        "silver_dataset_id",
        "gold_dataset_id",
        "quarantine_dataset_id",
        "assertions_dataset_id",
        "ops_telemetry_dataset_id",
    ):
        if values.get(field):
            _validate_pattern(field, values[field], DATASET_ID_RE)

    _validate_pattern(
        "landing_bucket_name", values["landing_bucket_name"], BUCKET_NAME_RE
    )
    _validate_dataform_repository(values["dataform_repository_name"])

    if values.get("dataform_release_config_name"):
        _validate_release_config(values["dataform_release_config_name"])

    for scan_field in ("dataplex_profile_scan_id", "dataplex_quality_scan_id"):
        if values.get(scan_field):
            _validate_dataplex_scan(scan_field, values[scan_field])

    for field in (
        "dataform_sa_email",
        "batch_loader_sa_email",
        "pubsub_writer_sa_email",
    ):
        if values.get(field):
            _validate_pattern(field, values[field], SA_EMAIL_RE)

    if values.get("kms_key_id"):
        _validate_pattern("kms_key_id", values["kms_key_id"], KMS_KEY_RE)
    if values.get("backup_vault_id"):
        _validate_pattern(
            "backup_vault_id", values["backup_vault_id"], BACKUP_VAULT_ID_RE
        )
    if values.get("vpc_id"):
        _validate_pattern("vpc_id", values["vpc_id"], VPC_ID_RE)
    if values.get("subnet_id"):
        _validate_pattern("subnet_id", values["subnet_id"], SUBNET_ID_RE)
    if values.get("datastream_network_attachment_id"):
        _validate_pattern(
            "datastream_network_attachment_id",
            values["datastream_network_attachment_id"],
            NETWORK_ATTACHMENT_RE,
        )
    if values.get("pii_restricted_policy_tag_id"):
        _validate_pattern(
            "pii_restricted_policy_tag_id",
            values["pii_restricted_policy_tag_id"],
            POLICY_TAG_RE,
        )
    if values.get("pii_masked_policy_tag_id"):
        _validate_pattern(
            "pii_masked_policy_tag_id",
            values["pii_masked_policy_tag_id"],
            POLICY_TAG_RE,
        )
    if values.get("artifact_registry_repository_uri"):
        _validate_pattern(
            "artifact_registry_repository_uri",
            values["artifact_registry_repository_uri"],
            ARTIFACT_REGISTRY_URI_RE,
        )
    if values.get("region"):
        _validate_pattern("region", values["region"], REGION_RE)
    if values.get("environment"):
        _validate_pattern("environment", values["environment"], ENVIRONMENT_RE)
    if values.get("prefix"):
        _validate_pattern("prefix", values["prefix"], PREFIX_RE)


def build_linked_tfvars(
    values: dict[str, str], target_variables_tf: Path | None = None
) -> dict[str, str]:
    linked: dict[str, str] = {}
    for key, val in values.items():
        if val:
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
    else:
        declared = INGESTION_DECLARED_VARS

    linked = {k: v for k, v in linked.items() if k in declared}
    return dict(sorted(linked.items()))


def write_atomic_json(output_path: Path, payload: dict[str, str]) -> None:
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

        values: dict[str, str] = {}
        if args.context is not None:
            values.update(load_context_values(args.context, target_env=target_env))
        elif target_env is not None:
            values["environment"] = target_env

        for field in FIELD_FLAGS:
            if field == "environment":
                continue
            cli_val = getattr(args, field, None)
            if cli_val is not None:
                cleaned = cli_val.strip()
                if cleaned:
                    values[field] = cleaned
                else:
                    values.pop(field, None)

        for primary, alias in ALIAS_PAIRS:
            cli_val = getattr(args, alias, None)
            if cli_val is not None:
                cleaned = cli_val.strip()
                if cleaned:
                    values[primary] = cleaned
                else:
                    values.pop(primary, None)

        validate_inputs(values)
        linked = build_linked_tfvars(values, args.target_variables_tf)
        write_atomic_json(args.output, linked)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {len(linked)} linked variable(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
