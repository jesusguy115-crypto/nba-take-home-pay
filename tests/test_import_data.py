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
        self.assertEqual({p.name for p in (self.skill / "assets").iterdir()}, set(IMPORTER.REQUIRED + (IMPORTER.CACHE,)))
        self.assertGreater(report["players"], 0)
        self.assertEqual((self.skill / "assets" / IMPORTER.CACHE).read_bytes(), (self.source / IMPORTER.CACHE).read_bytes())
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
