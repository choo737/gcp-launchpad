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
DATASET_ID_RE = re.compile(r"^[A-Za-z0-9_]{1,1024}$")
BUCKET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$")
ENVIRONMENT_RE = re.compile(r"^(dev|staging|prod)$")
PREFIX_RE = re.compile(r"^[a-z](?:[a-z0-9-]{0,6}[a-z0-9])$")
REGION_RE = re.compile(r"^[a-z]+-[a-z]+[0-9]+$")
DATAFORM_SHORT_RE = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
DATAFORM_PATH_RE = re.compile(
    r"^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/locations/[a-z0-9-]+/repositories/[A-Za-z0-9._-]+$"
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
    ("bi_project_id", "bi_compute_project_id"),
    ("gold_dataset_id", "primary_gold_dataset_id"),
    ("kms_key_id", "kms_key_name"),
    ("vpc_id", "network_id"),
    ("dataform_sa_email", "dataform_service_account_email"),
)


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
    for field in FIELD_FLAGS:
        flag = "--" + field.replace("_", "-")
        parser.add_argument(flag, dest=field, default=None)
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


def load_context_values(context_path: Path) -> dict[str, str]:
    if not context_path.is_file():
        raise FileNotFoundError(f"Context file not found: {context_path}")
    payload = json.loads(context_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("platform-context.json must contain a JSON object.")

    values: dict[str, str] = {}
    landing_zone = payload.get("existing_landing_zone")
    if landing_zone is not None:
        if not isinstance(landing_zone, dict):
            raise ValueError("existing_landing_zone must be a JSON object.")
        for key, raw_val in landing_zone.items():
            if key not in FIELD_FLAGS:
                continue
            if raw_val is None:
                continue
            if not isinstance(raw_val, str):
                raise ValueError(
                    f"existing_landing_zone.{key} must be a string, got {type(raw_val).__name__}"
                )
            if raw_val.strip():
                values[key] = raw_val.strip()

    top_level_mappings = (
        ("primary_region", "region"),
        ("prefix", "prefix"),
    )
    for src_key, dst_key in top_level_mappings:
        raw_val = payload.get(src_key)
        if dst_key not in values and isinstance(raw_val, str) and raw_val.strip():
            values[dst_key] = raw_val.strip()

    if "environment" not in values:
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
    for short_field in (
        "dataform_release_config_name",
        "dataplex_profile_scan_id",
        "dataplex_quality_scan_id",
    ):
        if values.get(short_field):
            _validate_pattern(short_field, values[short_field], DATAFORM_SHORT_RE)
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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        values: dict[str, str] = {}
        if args.context is not None:
            values.update(load_context_values(args.context))

        for field in FIELD_FLAGS:
            cli_val = getattr(args, field, None)
            if cli_val is not None:
                cleaned = cli_val.strip()
                if cleaned:
                    values[field] = cleaned
                else:
                    values.pop(field, None)

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
