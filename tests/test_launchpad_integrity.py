"""Verify gcp-launchpad structure, scripts, schemas, workflows, and prose hygiene."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent

SKIP_DIRS = frozenset({
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".venv",
})

SKIP_FILES = frozenset({
    ".DS_Store",
    "platform-context.json",
    "00_linked.auto.tfvars.json",
})

BINARY_EXTENSIONS = frozenset({
    ".webp",
    ".gif",
    ".png",
    ".jpg",
    ".jpeg",
})

REQUIRED_FILES = (
    "LICENSE",
    "CODEOWNERS",
    ".gitignore",
    "Makefile",
    "README.md",
    "QUESTIONNAIRE.md",
    "AGENTS.md",
    "CLAUDE.md",
    "assets/cloud-city-launchpad.webp",
    "assets/cloud-city-org-scanner.png",
    "docs/01-end-to-end-operational-playbook.md",
    "docs/02-template-documentation-standard.md",
    "docs/03-org-completeness-scanner-design.md",
    "examples/platform-context.greenfield.json",
    "examples/platform-context.brownfield.json",
    "scripts/preflight-check.sh",
    "scripts/generate-brownfield-link.py",
    ".agents/skills/route-architecture/SKILL.md",
    ".agents/skills/brownfield-bridge/SKILL.md",
    ".github/workflows/ci.yml",
    "tests/test_launchpad_integrity.py",
)

CANONICAL_README_H2_SECTIONS = [
    "## Template Suite Overview",
    "## Create Your Private Repository (Do Not Fork Publicly)",
    "## Architecture & Capabilities",
    "## 6-Step Enterprise Operationalization",
    "## AI Coding Agent Quickstart",
    "## CI/CD Workflows",
    "## Repository Layout",
    "## Quick Verification",
    "## Documentation Index",
    "## License",
]

# SHA-256 digests of normalized lowercase forbidden customer/internal tokens.
FORBIDDEN_TOKEN_SHA256 = frozenset({
    "28a6c9ad99acc2abeef4831da37cf37001345f05fa7327562ee4a9b167019b04",
    "bf2e17a1a6bc6728a531b1f29fc3e9344836b4ee2dbc4826d52e7fad1ab903b4",
    "a1ff4908fbe5168909d20652cd786c91f25e62668cb7704e00b76b48bbd77061",
    "39c55727348dc27b1dfcca0c18ef5b993b5c5d05c35e84dda10667ffbf4901dd",
    "b39879ae27ef3ea552c5b1ef0d2e27d31e1e86fd9000f8e790efac1d4d66993b",
    "f7bed5a9de858cf4a466529421cb2394beafac86339684ef34b831877a0ae5d9",
    "cfb193f5ee1e7027fe5cfaaac3069069112470cd1de7dde83c109cfadd078f5a",
    "7ce3b7e784772b32867cef471271a3ddf571d4197f8e0a948d9106fa8470b2fe",
    "d43e610ed1d8b1bdf2fc1d636d5db802e331d6c3e8467e65f26b1ed874f5ad55",
    "05bc6fa1ff0770f5de13c86f1d27418c938adea2dac09bf99680e8c31bf89c1c",
    "8d2d5be141e37e13f3eaa4a427c1c998eb2f3f9d66d22bb85322e4f5e1cc65f5",
    "ff395a42edbe5317b427b2d700de5be8c6452880ba9a46f66391de6907b887b2",
    "bcaeb7aaf13db3381e1c0c07ca7d7c9e0b58bb1a77aa177c420d9ddc1f42b72f",
    "eadba710424a7ccf76ee3a5b175ea916c5095c23e0c9eb73cd06e0bd391a88de",
    "ea3b268fa7164cf31bb5a5b7d5a70a1da3411e7d2bb36734dca05bd4d97e611d",
    "fc3fcf326138c3a556919d0e9e38100c7f3d8ead8a6a2f2b80af0bb3bc3e7ad7",
    "d4d98d8e8d9d1caf68c53b512ffa9add380e62dde5437cf9a3dec954b87e4bd1",
    "8aabce2e29396d5ce7e7ff8a0c76829c638938d3dd86642dfa8d4f7850492673",
    "159bc6a26ae434afaf52019da41182f185220ad04d4a330e4cd42c631f58adf8",
    "49abed4953748a8a9a8295f28fe864af4ce0d856e0fa9f69ee1a4463cb246239",
    "13ed7955a8035437bf820cb1d940b7c222b86030834d0aecf9333acfa50735b4",
    "4e41237f5f263ce5dc9566a6ba831e3b732297c006415ec51c16b440d4e7c962",
    "b0b70f066e82230c9ae95610a7aeec44a28f8cf4c6d2edb1e4e231027055469f",
    "d599e93c589788ef7cf53ec1c648cc1c64244ce66b8d1785aa5b7293a8d97a68",
    "42db212c2a8ab6fe26978fadcba7c6f3c8c9ae7a81a7af34930ca174fede649b",
    "4c77cac1139b0f6d8f1811079c7e14daf82696b71a8804722e9fc44a509c1fc4",
    "188e6a694d69c6728ad7ea2ba5b5553dda27478b1bc2e4bb7cc50850280742bd",
    "c4c86be45204a944b7d1ffe6d5adec4f8bdfb7784b45b6c24d78f6e3ed9bccca",
    "133937e4fbee1a2cc88b809af2ff3ff8a964a8f4c6cd5996af6d49b10c50d203",
})

LEAKED_IDENTIFIERS = (
    "/usr/local/" + "google/home/",
    "@" + "google.com",
    ".c.googlers." + "com",
)

SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:[A-Z]+ )?" + r"PRIVATE KEY-----"),
    re.compile(r"\bAK" + r"IA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh" + r"p_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAI" + r"za[0-9A-Za-z_-]{35}\b"),
)

TWELVE_DIGIT_RE = re.compile(r"\b\d{12}\b")
BILLING_ID_RE = re.compile(r"\b[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}\b")
DEPRECATED_MODEL_RE = re.compile(
    r"\b(?:gemini[- ]?(?:1\.0|1\.5|2\.0|2\.5)|claude[- ]?3|gemma[- ]?2)\b",
    re.IGNORECASE,
)

MOCK_MARKERS = (
    "mock_" + "success",
    "dummy_" + "payload",
    "fake_" + "output",
)

BANNED_AI_WORDS = (
    "del" + "ve",
    "navi" + "gate",
    "fos" + "ter",
    "cham" + "pion",
    "stream" + "line",
    "ele" + "vate",
    "har" + "ness",
    "orches" + "trate",
    "illu" + "minate",
    "tran" + "scend",
    "demy" + "stify",
    "emb" + "race",
    "un" + "lock",
    "tape" + "stry",
    "testa" + "ment",
    "bea" + "con",
    "re" + "alm",
    "land" + "scape",
    "para" + "digm",
    "syn" + "ergy",
    "fa" + "cet",
    "nua" + "nce",
    "corner" + "stone",
    "jour" + "ney",
    "blue" + "print",
    "para" + "mount",
    "multi" + "faceted",
    "vib" + "rant",
    "piv" + "otal",
    "hol" + "istic",
    "cru" + "cial",
    "compre" + "hensive",
    "meti" + "culous",
    "dyn" + "amic",
    "pro" + "found",
    "intr" + "icate",
    "further" + "more",
    "more" + "over",
    "in " + "conclusion",
    "at its " + "core",
    "it is worth " + "noting",
    "impor" + "tantly",
    "in " + "summary",
    "ulti" + "mately",
)

EMOJI_PATTERN = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]")
SECTION_SYMBOL = "\u00a7"
BULLET_PREFIX_RE = re.compile(r"^(?:[-*]|\d+\.)\s+")
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
ABBREV_DOT_RE = re.compile(r"\b(e|i)\.g\.", re.IGNORECASE)
TABLE_SEP_CELL_RE = re.compile(r"^:?-{3,}:?$")
WORD_TOKEN_RE = re.compile(r"[A-Za-z0-9_'-]+")


def _strip_md_links(text: str) -> str:
    return MD_LINK_RE.sub(r"\1", text)


def _iter_repo_files() -> list[Path]:
    files: list[Path] = []
    for path in sorted(REPO_ROOT.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in SKIP_FILES:
            continue
        if path.name.endswith((".tfstate", ".tfstate.backup")) or ".tfstate." in path.name:
            continue
        if path.suffix.lower() in BINARY_EXTENSIONS:
            continue
        files.append(path)
    return files


def _extract_markdown_sentences(text: str) -> list[str]:
    lines = text.splitlines()
    in_code = False
    in_frontmatter = False
    prose_blocks: list[str] = []
    current_para: list[str] = []

    def flush_para() -> None:
        if current_para:
            prose_blocks.append(" ".join(current_para))
            current_para.clear()

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if idx == 0 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue
        if stripped.startswith("```"):
            flush_para()
            in_code = not in_code
            continue
        if in_code:
            continue
        if not stripped or stripped.startswith(("#", "|", "---", "<picture", "</picture", "<source", "<img", "![")):
            flush_para()
            continue
        if stripped.startswith(">"):
            stripped = stripped.lstrip("> ").strip()
            if not stripped or stripped.startswith("[!"):
                flush_para()
                continue
        stripped = _strip_md_links(stripped)
        if BULLET_PREFIX_RE.match(stripped):
            flush_para()
            current_para.append(BULLET_PREFIX_RE.sub("", stripped).strip())
            continue
        current_para.append(stripped)

    flush_para()

    sentences: list[str] = []
    for block in prose_blocks:
        masked = ABBREV_DOT_RE.sub(lambda m: f"{m.group(1)}<DOT>g<DOT>", block)
        for part in re.split(r"[.!?](?:\s+|$)", masked):
            cleaned = part.replace("<DOT>", ".").strip()
            if cleaned:
                sentences.append(cleaned)
    return sentences


def _extract_markdown_table_cells(text: str) -> list[str]:
    lines = text.splitlines()
    in_code = False
    in_frontmatter = False
    cells: list[str] = []
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if idx == 0 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not stripped.startswith("|"):
            continue
        raw_cells = [c.strip() for c in stripped.strip("|").split("|")]
        if raw_cells and all(TABLE_SEP_CELL_RE.match(c) for c in raw_cells if c):
            continue
        for cell in raw_cells:
            cleaned = _strip_md_links(cell).strip()
            if cleaned:
                cells.append(cleaned)
    return cells


class LaunchpadIntegrityTest(unittest.TestCase):
    """Validate structure, agent docs, scripts, examples, CI, and anti-leak rules."""

    def test_required_files_and_no_catalog_yaml(self) -> None:
        for rel in REQUIRED_FILES:
            with self.subTest(file=rel):
                self.assertTrue((REPO_ROOT / rel).is_file(), f"Missing {rel}")
        self.assertFalse(
            (REPO_ROOT / "catalog.yaml").exists(),
            "catalog.yaml must not exist; README.md is the single catalog",
        )

    def test_gitignore_patterns(self) -> None:
        gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        for entry in (
            "platform-context.json",
            "terraform.tfvars",
            "*.auto.tfvars",
            "*.auto.tfvars.json",
            ".cm_project",
        ):
            with self.subTest(entry=entry):
                self.assertIn(entry, gitignore)
        for forbidden in ("*.tfvars", "*.tfvars.json"):
            self.assertNotIn(forbidden, gitignore)

    def test_readme_canonical_ten_sections(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertTrue(
            readme.startswith("# GCP Launchpad\n"),
            "README.md must start with '# GCP Launchpad'",
        )
        h2_sections = [
            line.strip() for line in readme.splitlines() if line.startswith("## ")
        ]
        self.assertEqual(h2_sections, CANONICAL_README_H2_SECTIONS)
        for required_link in (
            "QUESTIONNAIRE.md",
            "docs/01-end-to-end-operational-playbook.md",
            "docs/02-template-documentation-standard.md",
            "docs/03-org-completeness-scanner-design.md",
            "LICENSE",
        ):
            with self.subTest(link=required_link):
                self.assertIn(required_link, readme)

    def test_agent_instructions_align_and_roadmap_naming(self) -> None:
        required_refs = (
            "README.md",
            "QUESTIONNAIRE.md",
            "docs/01-end-to-end-operational-playbook.md",
            "docs/02-template-documentation-standard.md",
            "docs/03-org-completeness-scanner-design.md",
            "platform-context.json",
            "scripts/preflight-check.sh",
            "scripts/generate-brownfield-link.py",
            "route-architecture",
            "brownfield-bridge",
            "--private",
            "gcp-foundation",
            "gcp-data-ingestion",
            "gcp-data-medallion",
            "gcp-data-science",
            "gcp-webapp",
            "gcp-adk-agent",
        )
        for doc_name in ("AGENTS.md", "CLAUDE.md"):
            content = (REPO_ROOT / doc_name).read_text(encoding="utf-8")
            with self.subTest(doc=doc_name):
                for ref in required_refs:
                    self.assertIn(ref, content, f"{doc_name} missing {ref}")
        self.assertFalse((REPO_ROOT / "GEMINI.md").exists(), "GEMINI.md must not exist")

        stale_roadmap_name = "gcp-webapp-" + "ha"
        for path in _iter_repo_files():
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn(
                stale_roadmap_name,
                text,
                f"Use gcp-webapp instead of {stale_roadmap_name} in {path}",
            )

    def test_skills_have_valid_frontmatter(self) -> None:
        for skill_name in ("route-architecture", "brownfield-bridge"):
            skill_path = REPO_ROOT / ".agents" / "skills" / skill_name / "SKILL.md"
            text = skill_path.read_text(encoding="utf-8")
            with self.subTest(skill=skill_name):
                self.assertTrue(text.startswith("---\n"))
                parts = text.split("---\n", 2)
                self.assertGreaterEqual(len(parts), 3)
                frontmatter = parts[1]
                self.assertRegex(
                    frontmatter,
                    rf"(?m)^name:\s*{re.escape(skill_name)}\s*$",
                )
                self.assertRegex(frontmatter, r"(?m)^description:\s*.+$")

    def test_example_contexts_match_schema(self) -> None:
        required_keys = {
            "schema_version",
            "adoption_mode",
            "compliance_profile",
            "team_size_tier",
            "github_plan",
            "selected_templates",
            "primary_region",
            "dr_region",
            "environments",
            "prefix",
            "project_suffix",
            "github_owner",
            "ci_identity_mode",
            "existing_landing_zone",
        }
        for mode, filename in (
            ("greenfield", "examples/platform-context.greenfield.json"),
            ("brownfield", "examples/platform-context.brownfield.json"),
        ):
            payload = json.loads((REPO_ROOT / filename).read_text(encoding="utf-8"))
            with self.subTest(example=filename):
                self.assertEqual(payload["schema_version"], "1.0")
                self.assertEqual(payload["adoption_mode"], mode)
                self.assertTrue(required_keys.issubset(payload.keys()))
                self.assertIn(payload["team_size_tier"], ("S", "M", "L"))
                self.assertIn(
                    payload["github_plan"],
                    ("github_free", "github_team", "github_enterprise"),
                )
                self.assertRegex(payload["prefix"], r"^[a-z][a-z0-9-]{1,6}[a-z0-9]$")
                self.assertIn(payload["ci_identity_mode"], ("github_oidc_wif", "existing_ci_runner"))
                self.assertIsInstance(payload["selected_templates"], list)
                self.assertIsInstance(payload["environments"], list)
                self.assertIsInstance(payload["existing_landing_zone"], dict)

                finops = payload["finops"]
                self.assertEqual(
                    set(finops.keys()),
                    {
                        "create_dedicated_finops_project",
                        "finops_billing_export_location",
                        "monthly_budget_amount",
                        "environment_budgets",
                        "workload_budgets",
                        "budget_thresholds",
                        "enable_forecasted_threshold",
                        "finops_alert_email_addresses",
                    },
                )
                self.assertIsInstance(finops["create_dedicated_finops_project"], bool)
                self.assertIn(finops["finops_billing_export_location"], ("US", "EU", "asia-southeast1"))
                self.assertIsInstance(finops["monthly_budget_amount"], (int, float))
                self.assertNotIsInstance(finops["monthly_budget_amount"], bool)
                self.assertGreater(finops["monthly_budget_amount"], 0)
                self.assertIsInstance(finops["environment_budgets"], dict)
                self.assertTrue(finops["environment_budgets"])
                for amt in finops["environment_budgets"].values():
                    self.assertIsInstance(amt, (int, float))
                    self.assertNotIsInstance(amt, bool)
                    self.assertGreater(amt, 0)
                self.assertIsInstance(finops["workload_budgets"], dict)
                for wb in finops["workload_budgets"].values():
                    self.assertEqual(set(wb.keys()), {"amount", "projects", "labels", "alert_emails"})
                    self.assertIsInstance(wb["amount"], (int, float))
                    self.assertNotIsInstance(wb["amount"], bool)
                    self.assertGreater(wb["amount"], 0)
                    self.assertIsInstance(wb["projects"], list)
                    self.assertIsInstance(wb["labels"], dict)
                    self.assertIsInstance(wb["alert_emails"], list)
                self.assertIsInstance(finops["budget_thresholds"], list)
                self.assertTrue(finops["budget_thresholds"])
                for ratio in finops["budget_thresholds"]:
                    self.assertIsInstance(ratio, (int, float))
                    self.assertNotIsInstance(ratio, bool)
                    self.assertGreater(ratio, 0)
                    self.assertLessEqual(ratio, 1.0)
                self.assertIsInstance(finops["enable_forecasted_threshold"], bool)
                self.assertIsInstance(finops["finops_alert_email_addresses"], list)
                self.assertLessEqual(len(finops["finops_alert_email_addresses"]), 5)

                bdr = payload["backup_dr"]
                self.assertEqual(
                    set(bdr.keys()),
                    {
                        "enable_backup_dr",
                        "backup_enforced_retention_days",
                        "lock_backup_vault",
                        "soft_delete_retention_seconds",
                        "enable_dual_region_gcs",
                        "gcs_rpo",
                        "cross_border_dual_region_approved",
                        "bq_dr_mode",
                    },
                )
                for bkey in (
                    "enable_backup_dr",
                    "lock_backup_vault",
                    "enable_dual_region_gcs",
                    "cross_border_dual_region_approved",
                ):
                    self.assertIsInstance(bdr[bkey], bool)
                self.assertIn(bdr["backup_enforced_retention_days"], (14, 30))
                self.assertEqual(
                    bdr["soft_delete_retention_seconds"],
                    bdr["backup_enforced_retention_days"] * 86400,
                )
                self.assertIn(bdr["gcs_rpo"], ("DEFAULT", "ASYNC_TURBO"))
                self.assertIn(
                    bdr["bq_dr_mode"],
                    ("time_travel_only", "cross_region_replica", "enterprise_plus_failover"),
                )

                ngfw = payload["ngfw"]
                self.assertEqual(
                    set(ngfw.keys()),
                    {
                        "enable_hierarchical_firewall_policy",
                        "enable_ngfw_standard_rules",
                        "enable_secure_tags",
                        "enable_ngfw_enterprise",
                    },
                )
                for nkey in ngfw:
                    self.assertIsInstance(ngfw[nkey], bool)

                scc = payload["scc"]
                self.assertEqual(
                    set(scc.keys()),
                    {
                        "scc_tier",
                        "scc_scope",
                        "enable_audit_cmek",
                        "scc_alert_email_addresses",
                        "runtime_detectors",
                    },
                )
                self.assertIn(scc["scc_tier"], ("NONE", "STANDARD", "PREMIUM"))
                self.assertIn(scc["scc_scope"], ("FOLDER", "PROJECT"))
                self.assertIsInstance(scc["enable_audit_cmek"], bool)
                self.assertIsInstance(scc["scc_alert_email_addresses"], list)
                self.assertIsInstance(scc["runtime_detectors"], list)
                allowed_detectors = {
                    "EVENT_THREAT_DETECTION",
                    "CONTAINER_THREAT_DETECTION",
                    "VIRTUAL_MACHINE_THREAT_DETECTION",
                    "CLOUD_RUN_THREAT_DETECTION",
                }
                self.assertTrue(set(scc["runtime_detectors"]).issubset(allowed_detectors))

                ds = payload["data_science"]
                self.assertEqual(
                    set(ds.keys()),
                    {
                        "enable_data_science",
                        "ds_serving_track",
                        "enable_ds_workbench",
                        "enable_colab_enterprise",
                        "enable_online_feature_store",
                        "xai_audit_retention_days",
                        "shap_additivity_tolerance",
                        "fairness_min_disparate_impact",
                    },
                )
                for ds_bool_key in (
                    "enable_data_science",
                    "enable_ds_workbench",
                    "enable_colab_enterprise",
                    "enable_online_feature_store",
                ):
                    self.assertIsInstance(ds[ds_bool_key], bool)
                self.assertIn(
                    ds["ds_serving_track"],
                    ("bqml_batch", "vertex_cpr_online", "both"),
                )
                self.assertIsInstance(ds["xai_audit_retention_days"], int)
                self.assertNotIsInstance(ds["xai_audit_retention_days"], bool)
                self.assertGreater(ds["xai_audit_retention_days"], 0)
                self.assertIsInstance(ds["shap_additivity_tolerance"], (int, float))
                self.assertNotIsInstance(ds["shap_additivity_tolerance"], bool)
                self.assertGreater(ds["shap_additivity_tolerance"], 0)
                self.assertLessEqual(ds["shap_additivity_tolerance"], 0.001)
                self.assertIsInstance(ds["fairness_min_disparate_impact"], (int, float))
                self.assertNotIsInstance(ds["fairness_min_disparate_impact"], bool)
                self.assertGreater(ds["fairness_min_disparate_impact"], 0.0)
                self.assertLessEqual(ds["fairness_min_disparate_impact"], 1.0)
                self.assertIn("gcp-data-science", payload["selected_templates"])

        gf = json.loads(
            (REPO_ROOT / "examples" / "platform-context.greenfield.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(gf["compliance_profile"], "regulated_fsi_rmit")
        self.assertEqual(gf["team_size_tier"], "L")
        self.assertEqual(gf["github_plan"], "github_enterprise")
        self.assertTrue(gf["finops"]["create_dedicated_finops_project"])
        self.assertFalse(gf["backup_dr"]["enable_backup_dr"])
        self.assertEqual(gf["backup_dr"]["backup_enforced_retention_days"], 30)
        self.assertFalse(gf["backup_dr"]["lock_backup_vault"])
        self.assertEqual(gf["backup_dr"]["soft_delete_retention_seconds"], 2592000)
        self.assertFalse(gf["backup_dr"]["enable_dual_region_gcs"])
        self.assertEqual(gf["backup_dr"]["gcs_rpo"], "DEFAULT")
        self.assertFalse(gf["ngfw"]["enable_ngfw_enterprise"])
        self.assertEqual(gf["scc"]["scc_tier"], "PREMIUM")
        self.assertIn("VIRTUAL_MACHINE_THREAT_DETECTION", gf["scc"]["runtime_detectors"])
        self.assertTrue(gf["data_science"]["enable_data_science"])
        self.assertEqual(gf["data_science"]["ds_serving_track"], "both")
        self.assertTrue(gf["data_science"]["enable_ds_workbench"])
        self.assertFalse(gf["data_science"]["enable_colab_enterprise"])
        self.assertFalse(gf["data_science"]["enable_online_feature_store"])
        self.assertEqual(gf["data_science"]["xai_audit_retention_days"], 2555)
        self.assertEqual(gf["data_science"]["shap_additivity_tolerance"], 0.00001)
        self.assertEqual(gf["data_science"]["fairness_min_disparate_impact"], 0.80)

        bf = json.loads(
            (REPO_ROOT / "examples" / "platform-context.brownfield.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(bf["compliance_profile"], "enterprise_standard")
        self.assertEqual(bf["team_size_tier"], "M")
        self.assertEqual(bf["github_plan"], "github_team")
        self.assertTrue(bf["finops"]["create_dedicated_finops_project"])
        self.assertEqual(bf["backup_dr"]["backup_enforced_retention_days"], 14)
        self.assertFalse(bf["backup_dr"]["lock_backup_vault"])
        self.assertEqual(bf["backup_dr"]["soft_delete_retention_seconds"], 1209600)
        self.assertFalse(bf["backup_dr"]["enable_dual_region_gcs"])
        self.assertFalse(bf["ngfw"]["enable_ngfw_enterprise"])
        self.assertEqual(bf["scc"]["scc_tier"], "STANDARD")
        self.assertTrue(bf["data_science"]["enable_data_science"])
        self.assertEqual(bf["data_science"]["ds_serving_track"], "vertex_cpr_online")
        self.assertFalse(bf["data_science"]["enable_ds_workbench"])
        self.assertFalse(bf["data_science"]["enable_colab_enterprise"])
        self.assertTrue(bf["data_science"]["enable_online_feature_store"])
        self.assertEqual(bf["data_science"]["xai_audit_retention_days"], 365)
        self.assertEqual(bf["data_science"]["shap_additivity_tolerance"], 0.00001)
        self.assertEqual(bf["data_science"]["fairness_min_disparate_impact"], 0.80)
        for key in (
            "finops_project_id",
            "backup_project_id",
            "backup_vault_id",
            "ds_exp_project_id",
            "ml_ops_project_id",
            "ml_artifact_repo_id",
            "ml_audit_dataset_id",
            "ml_audit_table_id",
            "ml_worm_bucket_name",
            "silver_dataset_id",
            "by_environment",
        ):
            self.assertIn(key, bf["existing_landing_zone"])
        self.assertEqual(set(bf["existing_landing_zone"]["by_environment"].keys()), {"dev", "staging", "prod"})

    def test_questionnaire_four_pillars_and_official_links(self) -> None:
        questionnaire = (REPO_ROOT / "QUESTIONNAIRE.md").read_text(encoding="utf-8")
        expected_tokens = (
            "### Pillar 1: FinOps Governance & Billing Export",
            "### Pillar 2: Backup & Disaster Recovery",
            "### Pillar 3: Cloud NGFW & Network Security",
            "### Pillar 4: Security Command Center (SCC)",
            "<prefix>-cmn-finops",
            "finops_billing_export_location",
            "enable_backup_dr",
            "lock_backup_vault",
            "soft_delete_policy",
            "soft_delete_retention_seconds",
            "ASYNC_TURBO",
            "BNM RMiT",
            "ALTER SCHEMA ... ADD REPLICA",
            "GCE_FIREWALL",
            "enable_ngfw_enterprise",
            "SCC Enterprise",
            "May 21, 2027",
            "scc_scope",
            "VIRTUAL_MACHINE_THREAT_DETECTION",
            "<prefix>_scc_findings",
            "^[a-z][a-z0-9-]{1,6}[a-z0-9]$",
            "https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery-setup",
            "https://docs.cloud.google.com/docs/migration/plan/landing-zones",
            "https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery",
            "https://cloud.google.com/storage/sla",
            "https://cloud.google.com/security/products/firewall",
            "https://cloud.google.com/firewall/pricing",
            "## Section 7: Data Science & Regulated Explainable AI",
            "gcp-data-science",
            "ds_serving_track",
            "bqml_batch",
            "vertex_cpr_online",
            "ML.EXPLAIN_PREDICT",
            "TreeSHAP",
            "enable_ds_workbench",
            "enable_colab_enterprise",
            "enable_online_feature_store",
            "xai_audit_retention_days",
            "shap_additivity_tolerance",
            "fairness_min_disparate_impact",
            "model-validator",
            "ml_xai_audit_ledger",
            "March 2027",
            "https://cloud.google.com/vertex-ai/docs/deprecations",
            "https://cloud.google.com/bigquery/docs/xai-overview",
        )
        for token in expected_tokens:
            with self.subTest(token=token):
                self.assertIn(token, questionnaire)

    def test_preflight_script_cli_and_validation(self) -> None:
        script = REPO_ROOT / "scripts" / "preflight-check.sh"
        self.assertTrue(os.access(script, os.X_OK), "preflight-check.sh must be executable")

        help_res = subprocess.run(
            ["bash", str(script), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(help_res.returncode, 0, help_res.stderr)
        self.assertIn("Usage:", help_res.stdout)

        dry_res = subprocess.run(
            ["bash", str(script), "--dry-run", "--project", "example-core-01", "--region", "asia-southeast1"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(dry_res.returncode, 0, dry_res.stderr)
        self.assertIn("Dry-run mode enabled", dry_res.stdout)
        self.assertIn("gcloud compute regions describe asia-southeast1 --project=example-core-01", dry_res.stdout)

        dry_region_only = subprocess.run(
            ["bash", str(script), "--dry-run", "--region", "asia-southeast1"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(dry_region_only.returncode, 0, dry_region_only.stderr)
        self.assertIn("Planned check: gcloud compute regions", dry_region_only.stdout)

        for bad_args in (
            ["--dry-run", "--project", "BAD_ID!"],
            ["--dry-run", "--folder", "not-numeric"],
            ["--dry-run", "--org", "123"],
            ["--unknown-flag"],
        ):
            with self.subTest(bad_args=bad_args):
                bad_res = subprocess.run(
                    ["bash", str(script), *bad_args],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(bad_res.returncode, 0)

        for empty_or_missing in (
            ["--dry-run", "--project", ""],
            ["--dry-run", "--org-id", ""],
            ["--dry-run", "--region", ""],
            ["--dry-run", "--project"],
            ["--project", "--dry-run"],
            ["--project", "-h"],
            ["--dry-run", "--project="],
            ["--dry-run", "--org-id="],
            ["--dry-run", "--region="],
        ):
            with self.subTest(empty_or_missing=empty_or_missing):
                usage_res = subprocess.run(
                    ["bash", str(script), *empty_or_missing],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(usage_res.returncode, 2, usage_res.stderr)

        with tempfile.TemporaryDirectory() as tmp_dir:
            bin_dir = Path(tmp_dir) / "bin"
            bin_dir.mkdir()
            for tool_name, body in (
                ("gcloud", "#!/usr/bin/env bash\necho '(unset)'\n"),
                ("gh", "#!/usr/bin/env bash\nexit 0\n"),
                ("terraform", "#!/usr/bin/env bash\nexit 0\n"),
            ):
                tool_path = bin_dir / tool_name
                tool_path.write_text(body, encoding="utf-8")
                tool_path.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env['PATH']}"
            unset_res = subprocess.run(
                ["bash", str(script)],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(unset_res.returncode, 1)
            self.assertIn("No active gcloud account", unset_res.stderr)

            # Verify ACTIVE vs DELETE_REQUESTED lifecycleState and region checks with mocked gcloud.
            gcloud_mock = bin_dir / "gcloud"
            gcloud_mock.write_text(
                "#!/usr/bin/env python3\n"
                "import os, sys\n"
                "args = sys.argv[1:]\n"
                "if args[:3] == ['config', 'get-value', 'account']:\n"
                "    print('admin@example.com')\n"
                "elif args[:2] == ['projects', 'describe']:\n"
                "    print(os.environ.get('MOCK_PROJECT_STATE', 'ACTIVE'))\n"
                "elif args[:3] == ['resource-manager', 'folders', 'describe']:\n"
                "    print(os.environ.get('MOCK_FOLDER_STATE', 'ACTIVE'))\n"
                "elif args[:3] == ['compute', 'regions', 'describe']:\n"
                "    print('asia-southeast1\\tUP')\n"
                "elif args[:3] == ['compute', 'regions', 'list']:\n"
                "    print('asia-southeast1\\tUP')\n",
                encoding="utf-8",
            )
            gcloud_mock.chmod(0o755)

            ok_live = subprocess.run(
                [
                    "bash",
                    str(script),
                    "--project",
                    "example-core-01",
                    "--folder",
                    "12345678",
                    "--region",
                    "asia-southeast1",
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(ok_live.returncode, 0, ok_live.stderr)
            self.assertIn("Preflight checks passed", ok_live.stdout)

            del_proj_env = env.copy()
            del_proj_env["MOCK_PROJECT_STATE"] = "DELETE_REQUESTED"
            del_proj = subprocess.run(
                ["bash", str(script), "--project", "example-core-01"],
                env=del_proj_env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(del_proj.returncode, 1)
            self.assertIn("ERROR:", del_proj.stderr)
            self.assertIn("DELETE_REQUESTED", del_proj.stderr)

            del_folder_env = env.copy()
            del_folder_env["MOCK_FOLDER_STATE"] = "DELETE_REQUESTED"
            del_folder = subprocess.run(
                ["bash", str(script), "--folder", "12345678"],
                env=del_folder_env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(del_folder.returncode, 1)
            self.assertIn("ERROR:", del_folder.stderr)
            self.assertIn("DELETE_REQUESTED", del_folder.stderr)

    def test_generate_brownfield_link_end_to_end_and_filtering(self) -> None:
        script = REPO_ROOT / "scripts" / "generate-brownfield-link.py"
        self.assertTrue(
            os.access(script, os.X_OK),
            "generate-brownfield-link.py must be executable",
        )
        brownfield_ctx = REPO_ROOT / "examples" / "platform-context.brownfield.json"

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            out_file = tmp_root / "00_linked.auto.tfvars.json"
            res = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--context",
                    str(brownfield_ctx),
                    "--output",
                    str(out_file),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue(out_file.is_file())
            mode = stat.S_IMODE(out_file.stat().st_mode)
            self.assertEqual(mode, 0o600)

            linked = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertEqual(linked["core_project_id"], "acme-dev01-data-core")
            self.assertEqual(linked["core_storage_project_id"], "acme-dev01-data-core")
            self.assertEqual(linked["etl_compute_project_id"], "acme-dev01-data-etl")
            self.assertEqual(linked["primary_gold_project_id"], "acme-dev01-data-gold")
            self.assertEqual(linked["bi_project_id"], "acme-dev01-data-bi")
            self.assertNotIn("bi_compute_project_id", linked)
            self.assertNotIn("finops_project_id", linked)
            self.assertNotIn("backup_project_id", linked)
            self.assertNotIn("backup_vault_id", linked)
            self.assertEqual(linked["dataform_release_config_name"], "dev-main")
            self.assertEqual(linked["dataform_release_config_id"], "dev-main")
            self.assertEqual(linked["primary_gold_dataset_id"], "gold")
            self.assertEqual(linked["kms_key_name"], linked["kms_key_id"])
            self.assertEqual(linked["network_id"], linked["vpc_id"])
            self.assertEqual(
                linked["dataform_service_account_email"],
                linked["dataform_sa_email"],
            )

            # Verify unfiltered keys match gcp-data-ingestion/stages/enterprise/variables.tf when present on disk.
            committed_expected_keys = {
                "core_project_id",
                "core_storage_project_id",
                "compute_project_id",
                "etl_compute_project_id",
                "analytics_project_id",
                "primary_gold_project_id",
                "bi_project_id",
                "governance_project_id",
                "bronze_dataset_id",
                "silver_dataset_id",
                "gold_dataset_id",
                "primary_gold_dataset_id",
                "quarantine_dataset_id",
                "assertions_dataset_id",
                "ops_telemetry_dataset_id",
                "landing_bucket_name",
                "dataform_repository_name",
                "dataform_release_config_name",
                "dataform_release_config_id",
                "dataform_sa_email",
                "dataform_service_account_email",
                "batch_loader_sa_email",
                "pubsub_writer_sa_email",
                "kms_key_id",
                "kms_key_name",
                "manage_kms_iam",
                "pii_restricted_policy_tag_id",
                "pii_masked_policy_tag_id",
                "vpc_id",
                "network_id",
                "subnet_id",
                "artifact_registry_repository_uri",
                "region",
                "environment",
                "prefix",
            }
            self.assertEqual(set(linked.keys()), committed_expected_keys)
            self.assertIs(linked["manage_kms_iam"], False)

            spec = importlib.util.spec_from_file_location("generate_brownfield_link", script)
            self.assertIsNotNone(spec)
            assert spec is not None and spec.loader is not None
            gbl = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(gbl)

            # Hermetic check of INGESTION_DECLARED_VARS against FIELD_FLAGS, REQUIRED_FIELDS, and ALIAS_PAIRS.
            foundation_only_fields = frozenset(
                {"finops_project_id", "backup_project_id", "backup_vault_id"}
            )
            self.assertEqual(len(gbl.INGESTION_DECLARED_VARS), 77)
            self.assertTrue(set(gbl.REQUIRED_FIELDS).issubset(gbl.INGESTION_DECLARED_VARS))
            self.assertTrue(
                (set(gbl.FIELD_FLAGS) - foundation_only_fields).issubset(
                    gbl.INGESTION_DECLARED_VARS
                )
            )
            for primary, alias in gbl.ALIAS_PAIRS:
                self.assertIn(primary, gbl.INGESTION_DECLARED_VARS)
                self.assertIn(alias, gbl.INGESTION_DECLARED_VARS)

            ingestion_vars_tf = (
                REPO_ROOT.parent / "gcp-data-ingestion" / "stages" / "enterprise" / "variables.tf"
            )
            if ingestion_vars_tf.is_file():
                declared_vars = set(
                    re.findall(
                        r'^\s*variable\s+"([A-Za-z0-9_]+)"\s*\{',
                        ingestion_vars_tf.read_text(encoding="utf-8"),
                        re.MULTILINE,
                    )
                )
                self.assertEqual(gbl.INGESTION_DECLARED_VARS, declared_vars)
                self.assertTrue(
                    set(linked.keys()).issubset(declared_vars),
                    f"Undeclared keys for gcp-data-ingestion: {sorted(set(linked.keys()) - declared_vars)}",
                )

            # Verify --env and --environment staging/prod resolution from by_environment with zero dev01 leaks.
            for env_flag in ("--env", "--environment"):
                for target_env, expected_suffix in (("staging", "stg01"), ("prod", "prd01")):
                    with self.subTest(env_flag=env_flag, target_env=target_env):
                        env_out = tmp_root / f"{env_flag.lstrip('-')}-{target_env}.auto.tfvars.json"
                        env_res = subprocess.run(
                            [
                                sys.executable,
                                str(script),
                                "--context",
                                str(brownfield_ctx),
                                env_flag,
                                target_env,
                                "--output",
                                str(env_out),
                            ],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        self.assertEqual(env_res.returncode, 0, env_res.stderr)
                        raw_env_text = env_out.read_text(encoding="utf-8")
                        self.assertNotIn("dev01", raw_env_text)
                        env_linked = json.loads(raw_env_text)
                        self.assertEqual(env_linked["environment"], target_env)
                        self.assertEqual(
                            env_linked["core_project_id"],
                            f"acme-{expected_suffix}-data-core",
                        )
                        self.assertEqual(
                            env_linked["dataform_release_config_id"],
                            f"{target_env}-main",
                        )
                        self.assertIn(
                            f"acme-{expected_suffix}-data-gov",
                            env_linked["pii_restricted_policy_tag_id"],
                        )
                        self.assertIn(
                            f"acme-{expected_suffix}-data-gov",
                            env_linked["pii_masked_policy_tag_id"],
                        )

            # Verify conflicting --env/--environment and empty --env/--environment fail closed.
            for bad_env_args, expected_err in (
                (["--context", str(brownfield_ctx), "--env", "dev", "--environment", "staging"], "Conflicting"),
                (["--context", str(brownfield_ctx), "--env", ""], "Invalid environment ''"),
                (["--context", str(brownfield_ctx), "--environment", ""], "Invalid environment ''"),
            ):
                with self.subTest(bad_env_args=bad_env_args):
                    bad_env_res = subprocess.run(
                        [sys.executable, str(script), *bad_env_args, "--output", str(out_file)],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertNotEqual(bad_env_res.returncode, 0)
                    self.assertIn(expected_err, bad_env_res.stderr)

            # Verify by_environment empty string or null unsets inherited base keys.
            for unset_val in ("", None):
                with self.subTest(unset_val=unset_val):
                    unset_ctx = tmp_root / f"unset-{'none' if unset_val is None else 'empty'}.json"
                    unset_payload = json.loads(brownfield_ctx.read_text(encoding="utf-8"))
                    unset_payload["existing_landing_zone"]["by_environment"]["dev"]["kms_key_id"] = unset_val
                    unset_ctx.write_text(json.dumps(unset_payload), encoding="utf-8")
                    unset_out = tmp_root / "unset.auto.tfvars.json"
                    unset_res = subprocess.run(
                        [
                            sys.executable,
                            str(script),
                            "--context",
                            str(unset_ctx),
                            "--env",
                            "dev",
                            "--output",
                            str(unset_out),
                        ],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(unset_res.returncode, 0, unset_res.stderr)
                    unset_linked = json.loads(unset_out.read_text(encoding="utf-8"))
                    self.assertNotIn("kms_key_id", unset_linked)
                    self.assertNotIn("kms_key_name", unset_linked)

            # Verify RHS CLI alias flags normalize to LHS and conflicting LHS/RHS CLI flags fail closed.
            cli_alias_out = tmp_root / "cli-alias.auto.tfvars.json"
            cli_alias_res = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--core-storage-project-id",
                    "acme-dev01-data-core",
                    "--etl-compute-project-id",
                    "acme-dev01-data-etl",
                    "--primary-gold-project-id",
                    "acme-dev01-data-gold",
                    "--bronze-dataset-id",
                    "bronze",
                    "--primary-gold-dataset-id",
                    "gold",
                    "--landing-bucket-name",
                    "acme-dev01-raw-landing",
                    "--dataform-repository-name",
                    "medallion-repo",
                    "--dataform-release-config-id",
                    "dev-main",
                    "--dataform-service-account-email",
                    "sa-df@acme-dev01-data-etl.iam.gserviceaccount.com",
                    "--kms-key-name",
                    "projects/acme-dev01-data-gov/locations/asia-southeast1/keyRings/r/cryptoKeys/k",
                    "--network-id",
                    "projects/acme-dev01-network/global/networks/acme-vpc",
                    "--output",
                    str(cli_alias_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(cli_alias_res.returncode, 0, cli_alias_res.stderr)
            cli_alias_linked = json.loads(cli_alias_out.read_text(encoding="utf-8"))
            self.assertEqual(cli_alias_linked["core_project_id"], "acme-dev01-data-core")
            self.assertEqual(cli_alias_linked["compute_project_id"], "acme-dev01-data-etl")
            self.assertEqual(cli_alias_linked["analytics_project_id"], "acme-dev01-data-gold")
            self.assertEqual(cli_alias_linked["gold_dataset_id"], "gold")
            self.assertEqual(cli_alias_linked["dataform_release_config_name"], "dev-main")
            self.assertEqual(
                cli_alias_linked["dataform_sa_email"],
                "sa-df@acme-dev01-data-etl.iam.gserviceaccount.com",
            )
            self.assertIn("kms_key_id", cli_alias_linked)
            self.assertIn("vpc_id", cli_alias_linked)

            cli_conflict_res = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--context",
                    str(brownfield_ctx),
                    "--core-project-id",
                    "acme-dev01-data-core",
                    "--core-storage-project-id",
                    "acme-other-data-core",
                    "--output",
                    str(out_file),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(cli_conflict_res.returncode, 0)
            self.assertIn("Conflicting CLI flags", cli_conflict_res.stderr)

            # Verify RHS alias normalization works and unknown/conflicting keys fail closed.
            alias_ctx = tmp_root / "alias-context.json"
            alias_payload = json.loads(brownfield_ctx.read_text(encoding="utf-8"))
            alias_payload["existing_landing_zone"] = {
                "core_storage_project_id": "acme-dev01-data-core",
                "etl_compute_project_id": "acme-dev01-data-etl",
                "bronze_dataset_id": "bronze",
                "landing_bucket_name": "acme-dev01-raw-landing",
                "dataform_repository_name": "medallion-repo",
            }
            alias_ctx.write_text(json.dumps(alias_payload), encoding="utf-8")
            alias_out = tmp_root / "alias.auto.tfvars.json"
            alias_res = subprocess.run(
                [sys.executable, str(script), "--context", str(alias_ctx), "--output", str(alias_out)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(alias_res.returncode, 0, alias_res.stderr)
            self.assertEqual(
                json.loads(alias_out.read_text(encoding="utf-8"))["core_project_id"],
                "acme-dev01-data-core",
            )

            unknown_ctx = tmp_root / "unknown-key-context.json"
            unknown_payload = json.loads(brownfield_ctx.read_text(encoding="utf-8"))
            unknown_payload["existing_landing_zone"]["unexpected_typo_key"] = "oops"
            unknown_ctx.write_text(json.dumps(unknown_payload), encoding="utf-8")
            unknown_res = subprocess.run(
                [sys.executable, str(script), "--context", str(unknown_ctx), "--output", str(out_file)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(unknown_res.returncode, 0)
            self.assertIn("ERROR:", unknown_res.stderr)

            unknown_env_ctx = tmp_root / "unknown-env-key-context.json"
            unknown_env_payload = json.loads(brownfield_ctx.read_text(encoding="utf-8"))
            unknown_env_payload["existing_landing_zone"]["by_environment"]["prod"]["bad_key"] = "x"
            unknown_env_ctx.write_text(json.dumps(unknown_env_payload), encoding="utf-8")
            unknown_env_res = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--context",
                    str(unknown_env_ctx),
                    "--env",
                    "dev",
                    "--output",
                    str(out_file),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(unknown_env_res.returncode, 0)
            self.assertIn("ERROR:", unknown_env_res.stderr)

            # Verify optional Dataform, Dataplex, and Datastream fields pass validation and filter cleanly.
            ext_out = tmp_root / "extended.auto.tfvars.json"
            target_vars = tmp_root / "variables.tf"
            target_vars.write_text(
                'variable "core_storage_project_id" { type = string }\n'
                'variable "bronze_dataset_id" { type = string }\n'
                'variable "landing_bucket_name" { type = string }\n'
                'variable "dataform_release_config_name" { type = string }\n'
                'variable "dataplex_profile_scan_id" { type = string }\n'
                'variable "dataplex_quality_scan_id" { type = string }\n'
                'variable "datastream_network_attachment_id" { type = string }\n',
                encoding="utf-8",
            )
            ext_res = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--context",
                    str(brownfield_ctx),
                    "--dataform-release-config-name",
                    "prod-release",
                    "--dataplex-profile-scan-id",
                    "silver-orders-profile",
                    "--dataplex-quality-scan-id",
                    "silver-orders-dq",
                    "--datastream-network-attachment-id",
                    "projects/acme-dev01-network/regions/asia-southeast1/networkAttachments/ds-psc",
                    "--target-variables-tf",
                    str(target_vars),
                    "--output",
                    str(ext_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(ext_res.returncode, 0, ext_res.stderr)
            filtered = json.loads(ext_out.read_text(encoding="utf-8"))
            self.assertEqual(
                set(filtered.keys()),
                {
                    "bronze_dataset_id",
                    "core_storage_project_id",
                    "dataform_release_config_name",
                    "dataplex_profile_scan_id",
                    "dataplex_quality_scan_id",
                    "datastream_network_attachment_id",
                    "landing_bucket_name",
                },
            )

            # Verify full Dataform releaseConfig and Dataplex dataScans resource paths are accepted.
            full_path_out = tmp_root / "full-paths.auto.tfvars.json"
            full_rc = "projects/acme-dev01-data-etl/locations/asia-southeast1/repositories/medallion-repo/releaseConfigs/prod-main"
            full_prof = "projects/acme-dev01-data-gold/locations/asia-southeast1/dataScans/silver-orders-profile"
            full_qual = "projects/acme-dev01-data-gold/locations/asia-southeast1/dataScans/silver-orders-dq"
            full_res = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--context",
                    str(brownfield_ctx),
                    "--dataform-release-config-name",
                    full_rc,
                    "--dataplex-profile-scan-id",
                    full_prof,
                    "--dataplex-quality-scan-id",
                    full_qual,
                    "--output",
                    str(full_path_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(full_res.returncode, 0, full_res.stderr)
            full_linked = json.loads(full_path_out.read_text(encoding="utf-8"))
            self.assertEqual(full_linked["dataform_release_config_name"], full_rc)
            self.assertEqual(full_linked["dataform_release_config_id"], full_rc)
            self.assertEqual(full_linked["dataplex_profile_scan_id"], full_prof)
            self.assertEqual(full_linked["dataplex_quality_scan_id"], full_qual)

            # Verify conflicting LHS/RHS alias keys fail closed.
            conflict_ctx = tmp_root / "conflict-alias.json"
            conflict_payload = json.loads(brownfield_ctx.read_text(encoding="utf-8"))
            conflict_payload["existing_landing_zone"]["core_storage_project_id"] = "acme-other-core"
            conflict_ctx.write_text(json.dumps(conflict_payload), encoding="utf-8")
            conflict_res = subprocess.run(
                [sys.executable, str(script), "--context", str(conflict_ctx), "--output", str(out_file)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(conflict_res.returncode, 0)
            self.assertIn("Conflicting values", conflict_res.stderr)

            # Verify invalid identifiers, non-numeric policy tags, metacharacters, and missing fields fail cleanly.
            for bad_args in (
                ["--core-project-id", "BAD_PROJECT"],
                ["--bronze-dataset-id", "1bad_dataset"],
                ["--kms-key-id", "not/a/kms/key"],
                ["--kms-key-id", 'projects/acme-dev01-gov/locations/asia-southeast1/keyRings/ring"/cryptoKeys/key'],
                ["--vpc-id", "invalid-vpc"],
                ["--vpc-id", "projects/acme-dev01-net/global/networks/vpc;rm"],
                ["--subnet-id", "projects/acme-dev01-net/regions/asia-southeast1/subnetworks/sub$x"],
                ["--dataform-repository-name", "projects/acme-dev01-etl/locations/asia-southeast1/repositories/repo'x"],
                ["--dataform-repository-name", "projects/acme-dev01-etl/locations/asia-southeast1/repositories/repo.dot"],
                ["--context", str(brownfield_ctx), "--dataform-release-config-name", "projects/acme-dev01-etl/locations/asia-southeast1/repositories/medallion-repo/bad/prod"],
                ["--context", str(brownfield_ctx), "--dataplex-profile-scan-id", "BAD_SCAN"],
                ["--context", str(brownfield_ctx), "--dataplex-quality-scan-id", "BAD_SCAN"],
                ["--context", str(brownfield_ctx), "--env", "qa"],
                ["--pii-restricted-policy-tag-id", "projects/acme-dev01-data-gov/locations/asia-southeast1/taxonomies/example-tax-id/policyTags/12345678"],
                ["--pii-masked-policy-tag-id", "projects/acme-dev01-data-gov/locations/asia-southeast1/taxonomies/1000000001/policyTags/non-numeric"],
                ["--datastream-network-attachment-id", "projects/bad/global/networkAttachments/ds"],
                ["--prefix", "a-"],
                ["--prefix", "a"],
                ["--prefix", "ab"],
                ["--prefix", "toolongprefix"],
                ["--context", str(REPO_ROOT / "examples" / "platform-context.greenfield.json")],
            ):
                with self.subTest(bad_args=bad_args):
                    err_res = subprocess.run(
                        [sys.executable, str(script), *bad_args, "--output", str(out_file)],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertNotEqual(err_res.returncode, 0)

            # Verify non-string values in existing_landing_zone are rejected.
            bad_ctx = tmp_root / "bad-type-context.json"
            ctx_payload = json.loads(brownfield_ctx.read_text(encoding="utf-8"))
            ctx_payload["existing_landing_zone"]["bronze_dataset_id"] = 12345
            bad_ctx.write_text(json.dumps(ctx_payload), encoding="utf-8")
            type_res = subprocess.run(
                [sys.executable, str(script), "--context", str(bad_ctx), "--output", str(out_file)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(type_res.returncode, 0)
            self.assertIn("ERROR:", type_res.stderr)

            # Verify OSError (IsADirectoryError) exits cleanly without a Python traceback.
            dir_out = tmp_root / "existing_dir"
            dir_out.mkdir()
            os_res = subprocess.run(
                [sys.executable, str(script), "--context", str(brownfield_ctx), "--output", str(dir_out)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(os_res.returncode, 0)
            self.assertIn("ERROR:", os_res.stderr)
            self.assertNotIn("Traceback", os_res.stderr)

    def test_generate_brownfield_link_four_pillar_validation(self) -> None:
        script = REPO_ROOT / "scripts" / "generate-brownfield-link.py"
        brownfield_ctx = REPO_ROOT / "examples" / "platform-context.brownfield.json"

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            out_file = tmp_root / "pillar_linked.auto.tfvars.json"
            target_vars = tmp_root / "variables.tf"
            target_vars.write_text(
                'variable "finops_project_id" { type = string }\n'
                'variable "backup_project_id" { type = string }\n'
                'variable "backup_vault_id" { type = string }\n',
                encoding="utf-8",
            )
            override_vault = (
                "projects/acme-prod-cmn-backup/locations/asia-southeast1/backupVaults/prod-vault-02"
            )
            res = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--context",
                    str(brownfield_ctx),
                    "--finops-project-id",
                    "acme-prod-cmn-finops",
                    "--backup-project-id",
                    "acme-prod-cmn-backup",
                    "--backup-vault-id",
                    override_vault,
                    "--target-variables-tf",
                    str(target_vars),
                    "--output",
                    str(out_file),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(stat.S_IMODE(out_file.stat().st_mode), 0o600)
            linked = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertEqual(
                linked,
                {
                    "backup_project_id": "acme-prod-cmn-backup",
                    "backup_vault_id": override_vault,
                    "finops_project_id": "acme-prod-cmn-finops",
                },
            )

            for bad_args in (
                ["--context", str(brownfield_ctx), "--finops-project-id", "BAD_FINOPS"],
                ["--context", str(brownfield_ctx), "--finops-project-id", "ab"],
                ["--context", str(brownfield_ctx), "--backup-project-id", "BAD_BACKUP"],
                ["--context", str(brownfield_ctx), "--backup-vault-id", "not/a/vault"],
                [
                    "--context",
                    str(brownfield_ctx),
                    "--backup-vault-id",
                    "projects/acme-dev01-cmn-backup/locations/asia-southeast1/backupVaults/UPPER_BAD",
                ],
                [
                    "--context",
                    str(brownfield_ctx),
                    "--backup-vault-id",
                    "projects/acme-dev01-cmn-backup/locations/asia-southeast1/backupVaults/v",
                ],
            ):
                with self.subTest(bad_args=bad_args):
                    err_res = subprocess.run(
                        [sys.executable, str(script), *bad_args, "--output", str(out_file)],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertNotEqual(err_res.returncode, 0)
                    self.assertIn("ERROR:", err_res.stderr)

            for field in ("finops_project_id", "backup_project_id", "backup_vault_id"):
                for bad_val in (True, 42):
                    with self.subTest(field=field, bad_val=bad_val):
                        bad_ctx = tmp_root / f"bad-{field}-{type(bad_val).__name__}.json"
                        payload = json.loads(brownfield_ctx.read_text(encoding="utf-8"))
                        payload["existing_landing_zone"][field] = bad_val
                        bad_ctx.write_text(json.dumps(payload), encoding="utf-8")
                        type_res = subprocess.run(
                            [
                                sys.executable,
                                str(script),
                                "--context",
                                str(bad_ctx),
                                "--output",
                                str(out_file),
                            ],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        self.assertNotEqual(type_res.returncode, 0)
                        self.assertIn("ERROR:", type_res.stderr)

    def test_org_scanner_design_covers_d00_through_d16(self) -> None:
        scanner_doc = (
            REPO_ROOT / "docs" / "03-org-completeness-scanner-design.md"
        ).read_text(encoding="utf-8")
        self.assertIn("seventeen platform areas (`D00` through `D16`)", scanner_doc)
        self.assertIn("## 17-Area Control-Plane Checks", scanner_doc)
        for idx in range(17):
            check_id = f"`D{idx:02d}`"
            with self.subTest(check_id=check_id):
                self.assertIn(check_id, scanner_doc)
        for expected in (
            "<prefix>-cmn-finops",
            "BackupVault",
            "soft_delete_policy",
            "GCE_FIREWALL",
            "<prefix>_scc_findings",
            "Research lab & control tower",
            "ainotebooks.disableRootAccess",
            "disableFileDownloads",
            "explanationSpec",
            "FeatureOnlineStore",
            "ml_xai_audit_ledger",
            "roles/billing.viewer",
            "roles/backupdr.viewer",
            "roles/compute.viewer",
            "roles/resourcemanager.tagViewer",
            "roles/monitoring.viewer",
            "roles/securitycenter.adminViewer",
            "roles/aiplatform.viewer",
            "roles/notebooks.viewer",
            "Cloud Billing Account",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, scanner_doc)
        self.assertNotIn("roles/compute.networkViewer", scanner_doc)
        self.assertNotIn("roles/compute.orgFirewallPolicyUser", scanner_doc)

    def test_playbook_contains_complete_commands_and_variables(self) -> None:
        playbook = (REPO_ROOT / "docs" / "01-end-to-end-operational-playbook.md").read_text(
            encoding="utf-8"
        )
        for expected in (
            "foundation/01-org-governance foundation/02-security-network",
            "foundation/02-security-network data/enterprise/01-platform data/enterprise/02-governance-ops",
            "data/enterprise/03-data-science",
            "--from-gcs gs://<iac-outputs-bucket>/foundation-outputs.json",
            "--env dev",
            "--target data-science",
            "stages/enterprise",
            "gcp-data-science",
            "GCP_WIF_PROVIDER",
            "GCP_WIF_SERVICE_ACCOUNT",
            "GCP_ORG_GOV_WIF_SA",
            "GCP_NET_SEC_WIF_SA",
            "GCP_DATA_PLAT_WIF_SA",
            "GCP_DS_WIF_SA",
            "<prefix>_ops_telemetry.pipeline_runs",
            "make plan STAGE=<stage> ENV=<env> TFSTATE_BUCKET=<bucket>",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, playbook)

    def test_ci_workflow_security_hardening(self) -> None:
        workflow_files = sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))
        self.assertGreaterEqual(len(workflow_files), 1)
        for wf_path in workflow_files:
            ci_text = wf_path.read_text(encoding="utf-8")
            with self.subTest(workflow=wf_path.name):
                self.assertRegex(ci_text, r"(?m)^permissions:\s*\n\s*contents:\s*read\s*$")
                self.assertNotIn("write-all", ci_text)
                uses_refs = re.findall(r"(?m)^\s*uses:\s*([^\s#]+)", ci_text)
                self.assertGreaterEqual(len(uses_refs), 2)
                for ref in uses_refs:
                    with self.subTest(action_ref=ref):
                        self.assertRegex(ref, r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")

                in_perms_block = False
                perms_indent = 0
                in_run_block = False
                run_indent = 0
                for line in ci_text.splitlines():
                    stripped = line.lstrip()
                    indent = len(line) - len(stripped)
                    if in_perms_block:
                        if stripped and indent <= perms_indent:
                            in_perms_block = False
                        elif stripped and not stripped.startswith("#"):
                            self.assertNotRegex(
                                stripped,
                                r":\s*write\b",
                                f"{wf_path.name}: Unapproved write permission in permissions: {stripped}",
                            )
                    if re.match(r"^permissions\s*:", stripped):
                        self.assertNotRegex(
                            stripped,
                            r":\s*(?:write-all|write)\b",
                            f"{wf_path.name}: Write scope on permissions line: {stripped}",
                        )
                        in_perms_block = True
                        perms_indent = indent
                        continue

                    run_match = re.match(r"^(?:-\s*)?run\s*:\s*(.*)$", stripped)
                    if run_match:
                        self.assertNotIn("${{", stripped, f"{wf_path.name}: Expression interpolation inside run:")
                        run_rhs = re.sub(r"\s+#.*$", "", run_match.group(1)).strip()
                        if run_rhs in ("|", ">", "|-", ">-", "|+", ">+"):
                            in_run_block = True
                            run_indent = indent
                        continue
                    if in_run_block:
                        if stripped and indent <= run_indent:
                            in_run_block = False
                        else:
                            self.assertNotIn("${{", line, f"{wf_path.name}: Expression interpolation inside run: block")

    def test_no_leaked_identifiers_secrets_or_deprecated_models(self) -> None:
        alnum_re = re.compile(r"[a-z0-9]+")
        for path in _iter_repo_files():
            text = path.read_text(encoding="utf-8")
            lowered = text.lower()
            rel = str(path.relative_to(REPO_ROOT))
            with self.subTest(file=rel):
                for ident in LEAKED_IDENTIFIERS:
                    self.assertNotIn(
                        ident.lower(),
                        lowered,
                        f"Leaked identifier '{ident}' found in {rel}",
                    )
                tokens = alnum_re.findall(lowered)
                for idx, tok in enumerate(tokens):
                    digest = hashlib.sha256(tok.encode("utf-8")).hexdigest()
                    self.assertNotIn(digest, FORBIDDEN_TOKEN_SHA256, f"Forbidden token digest {digest} in {rel}")
                    if idx + 1 < len(tokens):
                        pair_digest = hashlib.sha256((tok + tokens[idx + 1]).encode("utf-8")).hexdigest()
                        self.assertNotIn(pair_digest, FORBIDDEN_TOKEN_SHA256, f"Forbidden token pair digest {pair_digest} in {rel}")
                for pat in SECRET_PATTERNS:
                    self.assertIsNone(
                        pat.search(text),
                        f"Secret pattern {pat.pattern} found in {rel}",
                    )
                self.assertIsNone(
                    TWELVE_DIGIT_RE.search(text),
                    f"Literal 12-digit integer found in {rel}",
                )
                self.assertIsNone(
                    BILLING_ID_RE.search(text),
                    f"Hex billing ID pattern found in {rel}",
                )
                self.assertIsNone(
                    DEPRECATED_MODEL_RE.search(text),
                    f"Deprecated model ID found in {rel}",
                )
                for marker in MOCK_MARKERS:
                    self.assertNotIn(
                        marker,
                        lowered,
                        f"Mock marker '{marker}' found in {rel}",
                    )

    def test_no_emojis_section_symbol_or_banned_ai_words(self) -> None:
        word_patterns = {
            w: re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE)
            for w in BANNED_AI_WORDS
        }
        for path in _iter_repo_files():
            text = path.read_text(encoding="utf-8")
            rel = str(path.relative_to(REPO_ROOT))
            with self.subTest(file=rel):
                self.assertIsNone(
                    EMOJI_PATTERN.search(text),
                    f"Decorative emoji found in {rel}",
                )
                self.assertNotIn(
                    SECTION_SYMBOL,
                    text,
                    f"Forbidden section symbol found in {rel}",
                )
                for word, pat in word_patterns.items():
                    self.assertIsNone(
                        pat.search(text),
                        f"Banned AI word '{word}' found in {rel}",
                    )

    def test_markdown_sentences_are_short(self) -> None:
        for path in _iter_repo_files():
            if path.suffix != ".md":
                continue
            rel = str(path.relative_to(REPO_ROOT))
            content = path.read_text(encoding="utf-8")
            sentences = _extract_markdown_sentences(content)
            table_cells = _extract_markdown_table_cells(content)
            with self.subTest(markdown=rel):
                for sentence in sentences:
                    words = [w for w in sentence.split() if w]
                    tokens = WORD_TOKEN_RE.findall(sentence)
                    self.assertLessEqual(
                        len(words),
                        20,
                        f"Sentence exceeds 20 words ({len(words)}) in {rel}: {sentence}",
                    )
                    self.assertLessEqual(
                        len(tokens),
                        20,
                        f"Sentence exceeds 20 word tokens ({len(tokens)}) in {rel}: {sentence}",
                    )
                for cell in table_cells:
                    words = [w for w in cell.split() if w]
                    tokens = WORD_TOKEN_RE.findall(cell)
                    self.assertLessEqual(
                        len(words),
                        20,
                        f"Table cell exceeds 20 words ({len(words)}) in {rel}: {cell}",
                    )
                    self.assertLessEqual(
                        len(tokens),
                        20,
                        f"Table cell exceeds 20 word tokens ({len(tokens)}) in {rel}: {cell}",
                    )

    def test_visual_assets_have_valid_headers(self) -> None:
        webp_path = REPO_ROOT / "assets" / "cloud-city-launchpad.webp"
        gif_path = REPO_ROOT / "assets" / "cloud-city-launchpad.gif"
        png_path = REPO_ROOT / "assets" / "cloud-city-org-scanner.png"

        for asset_path in (webp_path, png_path):
            with self.subTest(asset=str(asset_path.relative_to(REPO_ROOT))):
                self.assertTrue(asset_path.is_file(), f"Missing {asset_path}")
                self.assertGreater(asset_path.stat().st_size, 100_000)

        webp_head = webp_path.read_bytes()[:12]
        self.assertEqual(webp_head[:4], b"RIFF")
        self.assertEqual(webp_head[8:12], b"WEBP")

        self.assertFalse(gif_path.exists(), f"Duplicate GIF asset must not exist: {gif_path}")

        png_head = png_path.read_bytes()[:8]
        self.assertEqual(png_head, b"\x89PNG\r\n\x1a\n")

    def test_readme_and_questionnaire_tshirt_tiers_github_plan_and_cost_floor(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        questionnaire = (REPO_ROOT / "QUESTIONNAIRE.md").read_text(encoding="utf-8")

        for token in (
            "team_size_tier",
            "github_free",
            "github_team",
            "github_enterprise",
            "$0/mo",
            "$5,365.50/mo",
            "$2,555/mo/env",
            "CODEOWNERS",
            "Environment Required Reviewers",
        ):
            with self.subTest(readme_token=token):
                self.assertIn(token, readme)

        for token in (
            "team_size_tier",
            "github_plan",
            "github_free",
            "github_team",
            "github_enterprise",
            "asia-east2",
        ):
            with self.subTest(questionnaire_token=token):
                self.assertIn(token, questionnaire)

    def test_generate_brownfield_link_kms_iam_domain_export_gcs_and_print_commands(self) -> None:
        script = REPO_ROOT / "scripts" / "generate-brownfield-link.py"
        brownfield_ctx = REPO_ROOT / "examples" / "platform-context.brownfield.json"

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            out_file = tmp_root / "00_linked.auto.tfvars.json"

            # Verify --manage-kms-iam sets true, --no-manage-kms-iam sets false, and --domain-name emits domain_name.
            res_true = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--context",
                    str(brownfield_ctx),
                    "--manage-kms-iam",
                    "--domain-name",
                    "retail-pos",
                    "--output",
                    str(out_file),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res_true.returncode, 0, res_true.stderr)
            linked_true = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertIs(linked_true["manage_kms_iam"], True)
            self.assertEqual(linked_true["domain_name"], "retail-pos")

            # Verify context boolean manage_kms_iam = true is preserved and --no-manage-kms-iam overrides it.
            ctx_true_path = tmp_root / "ctx-kms-true.json"
            ctx_payload = json.loads(brownfield_ctx.read_text(encoding="utf-8"))
            ctx_payload["existing_landing_zone"]["manage_kms_iam"] = True
            ctx_true_path.write_text(json.dumps(ctx_payload), encoding="utf-8")

            res_ctx_true = subprocess.run(
                [sys.executable, str(script), "--context", str(ctx_true_path), "--output", str(out_file)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res_ctx_true.returncode, 0, res_ctx_true.stderr)
            self.assertIs(json.loads(out_file.read_text(encoding="utf-8"))["manage_kms_iam"], True)

            res_override_false = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--context",
                    str(ctx_true_path),
                    "--no-manage-kms-iam",
                    "--output",
                    str(out_file),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res_override_false.returncode, 0, res_override_false.stderr)
            self.assertIs(json.loads(out_file.read_text(encoding="utf-8"))["manage_kms_iam"], False)

            # Verify invalid domain_name and invalid --export-gcs fail closed.
            bad_domain = subprocess.run(
                [sys.executable, str(script), "--context", str(brownfield_ctx), "--domain-name", "BAD_DOMAIN", "--output", str(out_file)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(bad_domain.returncode, 0)

            for bad_uri in ("", "s3://bucket/a.json", "gs://ab/a.json", "gs://BAD_BUCKET/a.json"):
                with self.subTest(bad_uri=bad_uri):
                    bad_gcs = subprocess.run(
                        [sys.executable, str(script), "--context", str(brownfield_ctx), "--export-gcs", bad_uri, "--output", str(out_file)],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(bad_gcs.returncode, 2, bad_gcs.stderr)

            # Verify --export-gcs resolves env subpath and uploads via gcloud storage cp.
            bin_dir = tmp_root / "bin"
            bin_dir.mkdir()
            gcs_store = tmp_root / "gcs"
            gcs_store.mkdir()
            gcloud_shim = bin_dir / "gcloud"
            gcloud_shim.write_text(
                "#!/usr/bin/env python3\n"
                "import os, shutil, sys\n"
                "from pathlib import Path\n"
                "store = Path(os.environ['TEST_GCS_STORE'])\n"
                "args = sys.argv[1:]\n"
                "assert args[:2] == ['storage', 'cp']\n"
                "dest = store / args[3].removeprefix('gs://')\n"
                "dest.parent.mkdir(parents=True, exist_ok=True)\n"
                "shutil.copyfile(args[2], dest)\n",
                encoding="utf-8",
            )
            gcloud_shim.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env['PATH']}"
            env["TEST_GCS_STORE"] = str(gcs_store)

            exp_res = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--context",
                    str(brownfield_ctx),
                    "--env",
                    "staging",
                    "--export-gcs",
                    "gs://cust-iac-outputs/brownfield.json",
                    "--print-kms-commands",
                    "--output",
                    str(out_file),
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(exp_res.returncode, 0, exp_res.stderr)
            uploaded = gcs_store / "cust-iac-outputs" / "staging" / "brownfield.json"
            self.assertTrue(uploaded.is_file())
            self.assertEqual(json.loads(uploaded.read_text(encoding="utf-8"))["environment"], "staging")

            for expected_sa in (
                "COMPUTE_PROJECT_NUMBER=\"$(gcloud projects describe 'acme-stg01-data-etl' --format='value(projectNumber)')\"",
                "gcloud kms keys add-iam-policy-binding data-cmek --project=acme-stg01-data-gov --location=asia-southeast1 --keyring=data-ring",
                "service-${COMPUTE_PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com",
                "service-${COMPUTE_PROJECT_NUMBER}@gcp-sa-datastream.iam.gserviceaccount.com",
                "service-${COMPUTE_PROJECT_NUMBER}@gcp-sa-workflows.iam.gserviceaccount.com",
                "service-${COMPUTE_PROJECT_NUMBER}@serverless-robot-prod.iam.gserviceaccount.com",
                "sa-batch-loader@acme-stg01-data-etl.iam.gserviceaccount.com",
            ):
                self.assertIn(expected_sa, exp_res.stdout)
            self.assertNotIn("<COMPUTE_PROJECT_NUMBER>", exp_res.stdout)

            # Verify resolve_env_gcs_uri preserves shared/ paths across environments.
            spec = importlib.util.spec_from_file_location("generate_brownfield_link_shared", script)
            self.assertIsNotNone(spec)
            assert spec is not None and spec.loader is not None
            gbl = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(gbl)
            self.assertEqual(
                gbl.resolve_env_gcs_uri("gs://cust-iac-outputs/shared/01-org-governance-outputs.json", "dev"),
                "gs://cust-iac-outputs/shared/01-org-governance-outputs.json",
            )
            self.assertEqual(
                gbl.resolve_env_gcs_uri("gs://cust-iac-outputs/02-security-network-outputs.json", "dev"),
                "gs://cust-iac-outputs/dev/02-security-network-outputs.json",
            )

    def test_generate_brownfield_link_data_science_and_validation(self) -> None:
        script = REPO_ROOT / "scripts" / "generate-brownfield-link.py"
        brownfield_ctx = REPO_ROOT / "examples" / "platform-context.brownfield.json"
        greenfield_ctx = REPO_ROOT / "examples" / "platform-context.greenfield.json"

        spec = importlib.util.spec_from_file_location("generate_brownfield_link_ds", script)
        self.assertIsNotNone(spec)
        assert spec is not None and spec.loader is not None
        gbl = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gbl)

        expected_ds_vars = {
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
        }
        self.assertEqual(len(gbl.DATA_SCIENCE_DECLARED_VARS), 35)
        self.assertEqual(gbl.DATA_SCIENCE_DECLARED_VARS, expected_ds_vars)

        ds_vars_tf = (
            REPO_ROOT.parent / "gcp-data-science" / "stages" / "enterprise" / "variables.tf"
        )
        if ds_vars_tf.is_file():
            declared_ds_vars = set(
                re.findall(
                    r'^\s*variable\s+"([A-Za-z0-9_]+)"\s*\{',
                    ds_vars_tf.read_text(encoding="utf-8"),
                    re.MULTILINE,
                )
            )
            self.assertEqual(gbl.DATA_SCIENCE_DECLARED_VARS, declared_ds_vars)

        # Verify greenfield context passes validate_data_science_config directly.
        gf_payload = json.loads(greenfield_ctx.read_text(encoding="utf-8"))
        gbl.validate_data_science_config(gf_payload)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            out_file = tmp_root / "ds_linked.auto.tfvars.json"

            # Verify --target data-science --no-manage-kms-iam --print-kms-commands.
            ds_res = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--context",
                    str(brownfield_ctx),
                    "--target",
                    "data-science",
                    "--no-manage-kms-iam",
                    "--print-kms-commands",
                    "--output",
                    str(out_file),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(ds_res.returncode, 0, ds_res.stderr)
            self.assertEqual(stat.S_IMODE(out_file.stat().st_mode), 0o600)
            ds_linked = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertEqual(
                set(ds_linked.keys()),
                {
                    "core_project_id",
                    "create_ml_audit_ledger_table",
                    "ds_exp_project_id",
                    "ds_serving_track",
                    "enable_online_feature_store",
                    "environment",
                    "fairness_min_disparate_impact",
                    "kms_key_id",
                    "manage_kms_iam",
                    "ml_artifact_repo_id",
                    "ml_audit_dataset_id",
                    "ml_audit_table_id",
                    "ml_ops_project_id",
                    "ml_worm_bucket_name",
                    "prefix",
                    "region",
                    "shap_additivity_tolerance",
                    "silver_dataset_id",
                    "vpc_id",
                },
            )
            self.assertIs(ds_linked["create_ml_audit_ledger_table"], True)
            self.assertEqual(ds_linked["ds_exp_project_id"], "acme-dev01-ds-exp")
            self.assertEqual(ds_linked["ml_ops_project_id"], "acme-dev01-ml-ops")
            self.assertEqual(ds_linked["ds_serving_track"], "vertex_cpr_online")
            self.assertIs(ds_linked["enable_online_feature_store"], True)
            self.assertEqual(ds_linked["shap_additivity_tolerance"], 0.00001)
            self.assertEqual(ds_linked["fairness_min_disparate_impact"], 0.80)
            self.assertIs(ds_linked["manage_kms_iam"], False)
            self.assertNotIn("bronze_dataset_id", ds_linked)
            self.assertNotIn("landing_bucket_name", ds_linked)

            for expected_cmd in (
                "ML_OPS_PROJECT_NUMBER=\"$(gcloud projects describe 'acme-dev01-ml-ops' --format='value(projectNumber)')\"",
                "DS_EXP_PROJECT_NUMBER=\"$(gcloud projects describe 'acme-dev01-ds-exp' --format='value(projectNumber)')\"",
                "gcloud kms keys add-iam-policy-binding data-cmek --project=acme-dev01-data-gov --location=asia-southeast1 --keyring=data-ring",
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
            ):
                self.assertIn(expected_cmd, ds_res.stdout)

            # Verify --target data-science prints Shared VPC attachment and Cloud Run subnet IAM guidance when egress_connector_subnet_id is set.
            shared_vpc_out = tmp_root / "ds_shared_vpc.auto.tfvars.json"
            shared_vpc_res = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--context",
                    str(brownfield_ctx),
                    "--target",
                    "data-science",
                    "--egress-connector-subnet-id",
                    "projects/acme-dev01-network/regions/asia-southeast1/subnetworks/acme-ds-subnet",
                    "--output",
                    str(shared_vpc_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(shared_vpc_res.returncode, 0, shared_vpc_res.stderr)
            for expected_net_cmd in (
                "gcloud compute shared-vpc associated-projects add 'acme-dev01-ml-ops' --host-project='acme-dev01-network'",
                "gcloud compute networks subnets add-iam-policy-binding 'acme-ds-subnet' --project='acme-dev01-network' --region='asia-southeast1'",
                "service-${ML_OPS_PROJECT_NUMBER}@serverless-robot-prod.iam.gserviceaccount.com",
                "--role=roles/compute.networkUser",
            ):
                self.assertIn(expected_net_cmd, shared_vpc_res.stdout)

            # Verify staging/prod resolution for --target data-science has zero dev01 leaks.
            for target_env, expected_suffix in (("staging", "stg01"), ("prod", "prd01")):
                with self.subTest(target_env=target_env):
                    env_out = tmp_root / f"ds-{target_env}.auto.tfvars.json"
                    env_res = subprocess.run(
                        [
                            sys.executable,
                            str(script),
                            "--context",
                            str(brownfield_ctx),
                            "--target",
                            "data-science",
                            "--env",
                            target_env,
                            "--output",
                            str(env_out),
                        ],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(env_res.returncode, 0, env_res.stderr)
                    raw_text = env_out.read_text(encoding="utf-8")
                    self.assertNotIn("dev01", raw_text)
                    env_linked = json.loads(raw_text)
                    self.assertEqual(env_linked["ds_exp_project_id"], f"acme-{expected_suffix}-ds-exp")
                    self.assertEqual(env_linked["ml_ops_project_id"], f"acme-{expected_suffix}-ml-ops")
                    self.assertEqual(env_linked["ml_worm_bucket_name"], f"acme-{expected_suffix}-ml-worm")

            # Verify FSI Colab rejection, asia-southeast2 online Feature Store rejection, and FSI retention >= 2555.
            bad_cases = [
                (
                    "fsi_colab_true",
                    {
                        "compliance_profile": "regulated_fsi_rmit",
                        "data_science": {**gf_payload["data_science"], "enable_colab_enterprise": True},
                    },
                    "enable_colab_enterprise",
                ),
                (
                    "jakarta_online_feature_store",
                    {
                        "primary_region": "asia-southeast2",
                        "data_science": {**gf_payload["data_science"], "enable_online_feature_store": True},
                    },
                    "asia-southeast2",
                ),
                (
                    "fsi_low_retention",
                    {
                        "compliance_profile": "regulated_fsi_rmit",
                        "data_science": {**gf_payload["data_science"], "xai_audit_retention_days": 365},
                    },
                    "2555",
                ),
                (
                    "bad_shap_tolerance",
                    {
                        "data_science": {**gf_payload["data_science"], "shap_additivity_tolerance": 0.01},
                    },
                    "shap_additivity_tolerance",
                ),
                (
                    "bad_disparate_impact",
                    {
                        "data_science": {**gf_payload["data_science"], "fairness_min_disparate_impact": 1.2},
                    },
                    "fairness_min_disparate_impact",
                ),
                (
                    "bad_serving_track",
                    {
                        "data_science": {**gf_payload["data_science"], "ds_serving_track": "legacy_explain"},
                    },
                    "ds_serving_track",
                ),
                (
                    "extra_ds_key",
                    {
                        "data_science": {**gf_payload["data_science"], "extra_key": True},
                    },
                    "Invalid data_science keys",
                ),
            ]
            base_bf = json.loads(brownfield_ctx.read_text(encoding="utf-8"))
            for label, overrides, expected_err in bad_cases:
                with self.subTest(bad_case=label):
                    bad_ctx = tmp_root / f"{label}.json"
                    payload = {**base_bf, **overrides}
                    bad_ctx.write_text(json.dumps(payload), encoding="utf-8")
                    err_res = subprocess.run(
                        [
                            sys.executable,
                            str(script),
                            "--context",
                            str(bad_ctx),
                            "--target",
                            "data-science",
                            "--output",
                            str(out_file),
                        ],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertNotEqual(err_res.returncode, 0)
                    self.assertIn(expected_err, err_res.stderr)


if __name__ == "__main__":
    unittest.main()
