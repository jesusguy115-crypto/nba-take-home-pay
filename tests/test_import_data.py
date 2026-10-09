"""Integration tests use user-held snapshots only, copied into temporary directories."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("data_importer", ROOT / "import_data.py")
IMPORTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IMPORTER)


def directory_digest(path):
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if item.is_file():
            digest.update(str(item.relative_to(path)).encode())
            digest.update(item.read_bytes())
    return digest.hexdigest()


class ImportDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = Path(os.environ.get("NBA_IMPORT_TEST_SOURCE", str(IMPORTER.DEFAULT_SKILL / "assets")))
        if not all((cls.original / name).is_file() for name in IMPORTER.REQUIRED + (IMPORTER.CACHE,)):
            raise unittest.SkipTest("Set NBA_IMPORT_TEST_SOURCE to an existing complete assets export including its cache")
        cls.original_digest = directory_digest(cls.original)

    @classmethod
    def tearDownClass(cls):
        if directory_digest(cls.original) != cls.original_digest:
            raise AssertionError("Tests modified their original source data")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="nba-import-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        for name in IMPORTER.REQUIRED + (IMPORTER.CACHE,):
            shutil.copyfile(self.original / name, self.source / name)
        self.skill = self.root / "skill"
        shutil.copytree(IMPORTER.DEFAULT_SKILL / "scripts", self.skill / "scripts",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    def run_import(self, *extra):
        return subprocess.run([sys.executable, str(ROOT / "import_data.py"), "--source", str(self.source),
                               "--skill-path", str(self.skill), *extra], capture_output=True, text=True)

    def assert_no_staging(self):
        self.assertFalse(list(self.root.glob(".skill-import-*")))

    def test_import_existing_cache_and_query(self):
        (self.source / "extra-private-file.txt").write_text("must not be imported")
        result = self.run_import()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report["cache_rebuilt"])
        self.assertEqual({p.name for p in (self.skill / "assets").iterdir()}, set(IMPORTER.REQUIRED + (IMPORTER.CACHE, IMPORTER.UPDATE_REPORT, IMPORTER.UPDATE_HISTORY)))
        self.assertGreater(report["players"], 0)
        self.assertEqual(report["comparison_status"], "no_prior_cache")
        self.assertEqual(report["player_change_count"], report["players"])
        self.assertTrue(Path(report["update_report"]).is_file())
        self.assertTrue(Path(report["update_history"]).is_file())
        self.assertEqual((self.skill / "assets" / IMPORTER.CACHE).read_bytes(), (self.source / IMPORTER.CACHE).read_bytes())
        self.assert_no_staging()

    def test_incomplete_settlement_cache_is_rejected(self):
        path = self.source / IMPORTER.CACHE
        data = json.loads(path.read_text())
        data["estimates"][1].pop("contract_baseline")
        path.write_text(json.dumps(data))
        result = self.run_import()
        self.assertEqual(result.returncode, 2)
        self.assertIn("contract_baseline", result.stderr)
        self.assertFalse((self.skill / "assets").exists())
        self.assert_no_staging()

    def test_missing_required_input_preserves_existing_assets(self):
        old = self.skill / "assets"
        shutil.copytree(self.source, old)
        before = directory_digest(old)
        (self.source / IMPORTER.REQUIRED[2]).unlink()
        result = self.run_import("--force")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Missing required data", result.stderr)
        self.assertEqual(directory_digest(old), before)
        self.assertFalse(list(self.skill.glob("assets.backup-*")))

    def test_refuses_overwrite_without_force(self):
        old = self.skill / "assets"
        old.mkdir()
        (old / "keep.txt").write_text("existing user data")
        before = directory_digest(old)
        result = self.run_import()
        self.assertEqual(result.returncode, 2)
        self.assertIn("--force", result.stderr)
        self.assertEqual(directory_digest(old), before)

    def test_force_retains_original_backup(self):
        old = self.skill / "assets"
        old.mkdir()
        (old / "keep.txt").write_text("existing user data")
        before = directory_digest(old)
        result = self.run_import("--force")
        self.assertEqual(result.returncode, 0, result.stderr)
        backup = Path(json.loads(result.stdout)["backup"])
        self.assertEqual(directory_digest(backup), before)
        self.assertTrue((old / IMPORTER.CACHE).is_file())

    def test_stale_cache_does_not_replace_existing_assets(self):
        old = self.skill / "assets"
        old.mkdir()
        (old / "keep.txt").write_text("existing user data")
        before = directory_digest(old)
        with (self.source / IMPORTER.REQUIRED[0]).open("a") as handle:
            handle.write("\n")
        result = self.run_import("--force")
        self.assertEqual(result.returncode, 2)
        self.assertIn("fingerprint mismatch", result.stderr)
        self.assertEqual(directory_digest(old), before)
        self.assert_no_staging()

    def test_absent_cache_builds_in_staging(self):
        (self.source / IMPORTER.CACHE).unlink()
        result = self.run_import()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["cache_rebuilt"])
        self.assertTrue((self.skill / "assets" / IMPORTER.CACHE).is_file())
        self.assertFalse((self.source / IMPORTER.CACHE).exists())
        self.assert_no_staging()

    def test_salary_update_reports_delta_and_preserves_history(self):
        first = self.run_import()
        self.assertEqual(first.returncode, 0, first.stderr)
        assets = self.skill / "assets"
        old_cache = json.loads((assets / IMPORTER.CACHE).read_text())
        initial_history = json.loads((assets / IMPORTER.UPDATE_HISTORY).read_text())
        salary_path = self.source / IMPORTER.REQUIRED[0]
        salary = json.loads(salary_path.read_text())
        player = salary["players"][0]
        player_id = player["player_id"]
        player["cash_total_usd"] += 100000
        payment = next(row for row in salary["payment_records"]
                       if row["record_id"] == player["payment_record_ids"][0])
        payment["cash_total_usd"] += 100000
        salary_path.write_text(json.dumps(salary, ensure_ascii=False), encoding="utf-8")
        (self.source / IMPORTER.CACHE).unlink()
        result = self.run_import("--force")
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertTrue(output["cache_rebuilt"])
        report = json.loads(Path(output["update_report"]).read_text())
        history = json.loads(Path(output["update_history"]).read_text())
        new_cache = json.loads((assets / IMPORTER.CACHE).read_text())
        old_player = next(row for row in old_cache["estimates"] if row["player_id"] == player_id)
        new_player = next(row for row in new_cache["estimates"] if row["player_id"] == player_id)
        change = next(row for row in report["player_changes"] if row["player_id"] == player_id)
        self.assertEqual(report["comparison_status"], "versioned_comparison")
        self.assertEqual(report["input_versions"]["salary"]["status"], "changed")
        self.assertEqual(report["player_change_count"], 1)
        self.assertIn("salary_changed", change["observed_changes"])
        self.assertEqual(change["amounts"]["gross_usd"]["delta_usd"], 94520)  # $100k contract increase after 5.48% reference reduction
        self.assertEqual(change["amounts"]["estimated_net_usd"]["delta_usd"],
                         round(new_player["estimated_net_usd"] - old_player["estimated_net_usd"], 2))
        self.assertEqual(history["reports"][:-1], initial_history["reports"])
        self.assertEqual(history["reports"][-1]["report_id"], report["report_id"])
        self.assert_no_staging()

        # Importing a supplied, unchanged cache still writes a latest report,
        # while retaining history without a duplicate no-change entry.
        shutil.copyfile(assets / IMPORTER.CACHE, self.source / IMPORTER.CACHE)
        repeated = self.run_import("--force")
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        repeated_output = json.loads(repeated.stdout)
        self.assertFalse(repeated_output["cache_rebuilt"])
        self.assertEqual(repeated_output["player_change_count"], 0)
        self.assertEqual(json.loads((assets / IMPORTER.UPDATE_HISTORY).read_text()), history)
        self.assertEqual(json.loads((assets / IMPORTER.UPDATE_REPORT).read_text())["player_change_count"], 0)
        self.assert_no_staging()

    def test_invalid_previous_history_leaves_assets_untouched(self):
        old = self.skill / "assets"
        shutil.copytree(self.source, old)
        (old / IMPORTER.UPDATE_HISTORY).write_text("{invalid history", encoding="utf-8")
        before = directory_digest(old)
        result = self.run_import("--force")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(directory_digest(old), before)
        self.assertFalse(list(self.skill.glob("assets.backup-*")))
        self.assert_no_staging()

    def test_installed_skill_entry_defaults_to_its_own_directory(self):
        shutil.copyfile(ROOT / "import_data.py", self.skill / "import_data.py")
        shutil.copyfile(IMPORTER.DEFAULT_SKILL / "SKILL.md", self.skill / "SKILL.md")
        result = subprocess.run([sys.executable, str(self.skill / "import_data.py"),
                                 "--source", str(self.source)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(json.loads(result.stdout)["assets"]), (self.skill / "assets").resolve())

    def test_install_rename_failure_restores_old_directory(self):
        old = self.skill / "assets"
        old.mkdir()
        (old / "keep.txt").write_text("existing user data")
        before = directory_digest(old)
        original_rename = Path.rename

        def fail_install(path, target):
            if path.name == "assets" and path.parent.name.startswith(".skill-import-"):
                raise OSError("simulated install rename failure")
            return original_rename(path, target)

        with mock.patch.object(Path, "rename", fail_install):
            with self.assertRaisesRegex(OSError, "simulated install rename failure"):
                IMPORTER.import_data(self.source, self.skill, force=True)
        self.assertEqual(directory_digest(old), before)
        self.assertFalse(list(self.skill.glob("assets.backup-*")))
        self.assert_no_staging()


if __name__ == "__main__":
    unittest.main()
