from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from auditflow.commands.evidence import (
    EvidenceManifestError,
    compare_evidence,
    load_evidence_manifest,
    refresh_evidence_manifest,
)
from auditflow.commands.init_project import create_initial_project
from auditflow.commands.validate import ValidationResult, validate_evidence_manifest


class EvidenceManifestTests(unittest.TestCase):
    def make_project(self) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        evidence_dir = root / "04_evidence"
        (evidence_dir / "02_raw_data").mkdir(parents=True)
        (evidence_dir / "01_regulations").mkdir(parents=True)
        (evidence_dir / "02_raw_data" / "scripts").mkdir(parents=True)
        (evidence_dir / "README.md").write_text("Folder instructions", encoding="utf-8")
        (evidence_dir / "02_raw_data" / "transactions.csv").write_text(
            "id,amount\n1,100\n",
            encoding="utf-8",
        )
        (evidence_dir / "01_regulations" / "policy.txt").write_text(
            "Approved policy version 1",
            encoding="utf-8",
        )
        (evidence_dir / "02_raw_data" / "scripts" / "extract.sql").write_text(
            "select * from transactions;",
            encoding="utf-8",
        )
        return root

    def test_refresh_records_hashes_without_metadata_files(self) -> None:
        root = self.make_project()

        result = refresh_evidence_manifest(root)
        records = load_evidence_manifest(root)

        self.assertTrue(result.changed)
        self.assertEqual(
            [record.path for record in records],
            ["01_regulations/policy.txt", "02_raw_data/transactions.csv"],
        )
        self.assertTrue(all(len(record.sha256) == 64 for record in records))
        self.assertTrue(compare_evidence(root).clean)

        second_refresh = refresh_evidence_manifest(root)
        self.assertFalse(second_refresh.changed)
        self.assertFalse(second_refresh.previous_changes)

    def test_comparison_reports_added_modified_and_missing_files(self) -> None:
        root = self.make_project()
        refresh_evidence_manifest(root)
        evidence_dir = root / "04_evidence"

        (evidence_dir / "02_raw_data" / "transactions.csv").write_text(
            "id,amount\n1,999\n",
            encoding="utf-8",
        )
        (evidence_dir / "01_regulations" / "policy.txt").unlink()
        (evidence_dir / "02_raw_data" / "new.csv").write_text(
            "id\n2\n",
            encoding="utf-8",
        )

        comparison = compare_evidence(root)

        self.assertEqual(
            {(change.kind, change.path) for change in comparison.changes},
            {
                ("added", "02_raw_data/new.csv"),
                ("missing", "01_regulations/policy.txt"),
                ("modified", "02_raw_data/transactions.csv"),
            },
        )

    def test_invalid_manifest_path_is_rejected(self) -> None:
        root = self.make_project()
        manifest_path = root / "04_evidence" / "evidence_manifest.yml"
        manifest_path.write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "hash_algorithm": "sha256",
                    "files": [
                        {
                            "path": "../outside.csv",
                            "sha256": "0" * 64,
                            "size_bytes": 1,
                        }
                    ],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(EvidenceManifestError, "safe relative path"):
            load_evidence_manifest(root)

    def test_validation_silently_skips_optional_missing_manifest(self) -> None:
        root = self.make_project()
        result = ValidationResult()

        validate_evidence_manifest(root, result)

        self.assertFalse(result.errors)
        self.assertFalse(result.warnings)

    def test_init_keeps_manifest_optional_and_ignores_private_evidence(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name) / "audit"

        create_initial_project(root)

        ignore_text = (root / ".gitignore").read_text(encoding="utf-8")
        self.assertFalse((root / "04_evidence" / "evidence_manifest.yml").exists())
        self.assertIn("04_evidence/**", ignore_text)
        self.assertIn("!04_evidence/evidence_manifest.yml", ignore_text)
        self.assertIn("!04_evidence/02_raw_data/scripts/**", ignore_text)


if __name__ == "__main__":
    unittest.main()
