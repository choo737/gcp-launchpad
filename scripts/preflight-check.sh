#!/usr/bin/env bash
set -euo pipefail

PROJECT_RE='^[a-z][a-z0-9-]{4,28}[a-z0-9]$'
FOLDER_ID_RE='^(folders/)?[0-9]{6,25}$'
ORG_ID_RE='^(organizations/)?[0-9]{6,25}$'
REGION_RE='^[a-z]+-[a-z]+[0-9]+$'

usage() {
  cat <<'EOF'
Usage:
  preflight-check.sh [--dry-run] [--project <id>] [--folder <id>] [--org <id>] [--region <region>] [-h|--help]

Options:
  --project <id>     Validate and inspect a GCP project ID.
  --folder <id>      Validate and inspect a numeric GCP folder ID.
  --org <id>         Validate and inspect a numeric GCP organization ID.
  --org-id <id>      Alias for --org.
  --region <region>  Validate a GCP region name (for example asia-southeast1).
  --dry-run          Validate flags and print planned read-only checks without network calls.
  -h, --help         Show this help message and exit.
EOF
}

die() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

die_usage() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 2
}

require_arg_value() {
  local flag="$1"
  local remaining="$2"
  local value="${3:-}"
  if [ "$remaining" -lt 2 ] || [ -z "$value" ] || [[ "$value" == -* ]]; then
    die_usage "Missing or empty value for ${flag}"
  fi
}

require_inline_value() {
  local flag="$1"
  local value="$2"
  if [ -z "$value" ] || [[ "$value" == -* ]]; then
    die_usage "Missing or empty value for ${flag}"
  fi
}

dry_run=false
project_id=""
folder_id=""
org_id=""
region=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run)
      dry_run=true
      shift
      ;;
    --project)
      require_arg_value "$1" "$#" "${2:-}"
      project_id="$2"
      shift 2
      ;;
    --project=*)
      project_id="${1#--project=}"
      require_inline_value "--project" "$project_id"
      shift
      ;;
    --folder)
      require_arg_value "$1" "$#" "${2:-}"
      folder_id="$2"
      shift 2
      ;;
    --folder=*)
      folder_id="${1#--folder=}"
      require_inline_value "--folder" "$folder_id"
      shift
      ;;
    --org|--org-id)
      require_arg_value "$1" "$#" "${2:-}"
      org_id="$2"
      shift 2
      ;;
    --org=*|--org-id=*)
      org_id="${1#*=}"
      require_inline_value "${1%%=*}" "$org_id"
      shift
      ;;
    --region)
      require_arg_value "$1" "$#" "${2:-}"
      region="$2"
      shift 2
      ;;
    --region=*)
      region="${1#--region=}"
      require_inline_value "--region" "$region"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die_usage "Unknown argument: $1"
      ;;
  esac
done

if [ -n "$project_id" ] && [[ ! "$project_id" =~ $PROJECT_RE ]]; then
  die "Invalid --project ID '${project_id}'. Must match ${PROJECT_RE}"
fi

if [ -n "$folder_id" ]; then
  if [[ ! "$folder_id" =~ $FOLDER_ID_RE ]]; then
    die "Invalid --folder ID '${folder_id}'. Must match ${FOLDER_ID_RE}"
  fi
  folder_id="${folder_id#folders/}"
fi

if [ -n "$org_id" ]; then
  if [[ ! "$org_id" =~ $ORG_ID_RE ]]; then
    die "Invalid --org ID '${org_id}'. Must match ${ORG_ID_RE}"
  fi
  org_id="${org_id#organizations/}"
fi

if [ -n "$region" ] && [[ ! "$region" =~ $REGION_RE ]]; then
  die "Invalid --region '${region}'. Must match ${REGION_RE}"
fi

tools=(gcloud terraform gh python3)
missing_tools=()

printf '==> Tool presence check\n'
for tool in "${tools[@]}"; do
  if command -v "$tool" >/dev/null 2>&1; then
    tool_path="$(command -v "$tool")"
    printf '  [OK] %s (%s)\n' "$tool" "$tool_path"
  else
    printf '  [MISSING] %s\n' "$tool"
    missing_tools+=("$tool")
  fi
done

if [ "$dry_run" = true ]; then
  printf '==> Dry-run mode enabled: skipping network and auth calls\n'
  printf '  Planned check: gcloud config get-value account --quiet\n'
  printf '  Planned check: gcloud auth application-default print-access-token --quiet\n'
  printf '  Planned check: gh auth status\n'
  if [ -n "$project_id" ]; then
    printf '  Planned check: gcloud projects describe %s --quiet\n' "$project_id"
  fi
  if [ -n "$folder_id" ]; then
    printf '  Planned check: gcloud resource-manager folders describe %s --quiet\n' "$folder_id"
  fi
  if [ -n "$org_id" ]; then
    printf '  Planned check: gcloud organizations describe %s --quiet\n' "$org_id"
  fi
  if [ -n "$region" ]; then
    if [ -n "$project_id" ]; then
      printf '  Planned check: gcloud compute regions describe %s --project=%s --quiet\n' "$region" "$project_id"
    else
      printf '  Planned check: gcloud compute regions list --filter=name=%s --quiet (skipped if no default project is configured)\n' "$region"
    fi
  fi
  exit 0
fi

if [ "${#missing_tools[@]}" -gt 0 ]; then
  die "Missing required tools for live preflight: ${missing_tools[*]}"
fi

export CLOUDSDK_CORE_DISABLE_PROMPTS=1

printf '==> Checking active gcloud account\n'
active_account="$(gcloud config get-value account --quiet 2>/dev/null || true)"
if [ -z "$active_account" ] || [ "$active_account" = "(unset)" ]; then
  die "No active gcloud account found. Run gcloud auth login first."
fi
printf '  Active gcloud account: %s\n' "$active_account"

printf '==> Checking Application Default Credentials (ADC)\n'
if gcloud auth application-default print-access-token --quiet >/dev/null 2>&1; then
  printf '  ADC credentials verified.\n'
else
  printf '  [WARN] Application Default Credentials (ADC) not configured or expired.\n'
  printf '  Remediation: run `gcloud auth application-default login` before running Terraform.\n'
fi

printf '==> Checking GitHub CLI authentication\n'
if ! gh auth status >/dev/null 2>&1; then
  die "GitHub CLI is not authenticated. Run gh auth login first."
fi
printf '  GitHub CLI authentication verified.\n'

if [ -n "$project_id" ]; then
  printf '==> Checking project visibility: %s\n' "$project_id"
  project_state="$(gcloud projects describe "$project_id" --format='value(lifecycleState)' --quiet)"
  printf '  Project %s lifecycleState: %s\n' "$project_id" "${project_state:-<empty>}"
  if [ "$project_state" != "ACTIVE" ]; then
    die "Project '${project_id}' is not ACTIVE (lifecycleState='${project_state:-unknown}')."
  fi
fi

if [ -n "$folder_id" ]; then
  printf '==> Checking folder visibility: %s\n' "$folder_id"
  folder_state="$(gcloud resource-manager folders describe "$folder_id" --format='value(lifecycleState)' --quiet)"
  printf '  Folder %s lifecycleState: %s\n' "$folder_id" "${folder_state:-<empty>}"
  if [ "$folder_state" != "ACTIVE" ]; then
    die "Folder '${folder_id}' is not ACTIVE (lifecycleState='${folder_state:-unknown}')."
  fi
fi

if [ -n "$org_id" ]; then
  printf '==> Checking organization visibility: %s\n' "$org_id"
  gcloud organizations describe "$org_id" --format='value(name,displayName)' --quiet
fi

if [ -n "$region" ]; then
  if [ -n "$project_id" ]; then
    printf '==> Checking region availability: %s (project: %s)\n' "$region" "$project_id"
    gcloud compute regions describe "$region" --project="$project_id" --format='value(name,status)' --quiet
  else
    printf '==> Checking region availability: %s\n' "$region"
    default_project="$(gcloud config get-value project --quiet 2>/dev/null || true)"
    if [ -z "$default_project" ] || [ "$default_project" = "(unset)" ]; then
      printf "  [SKIP] No --project set; validated region format '%s' offline\n" "$region"
    else
      region_match="$(gcloud compute regions list --filter="name=${region}" --format='value(name,status)' --quiet)"
      if [ -z "$region_match" ]; then
        die "Region '${region}' not found via gcloud compute regions list."
      fi
      printf '  %s\n' "$region_match"
    fi
  fi
fi

printf 'Preflight checks passed.\n'
