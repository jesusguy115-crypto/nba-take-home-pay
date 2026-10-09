"""Installation safety tests using temporary, non-financial fixture data only."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import shutil
import tempfile
import unittest
from unittest import mock


SPEC = importlib.util.spec_from_file_location(
    "nba_skill_installer", Path(__file__).resolve().parents[1] / "install.py"
)
installer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = installer
SPEC.loader.exec_module(installer)


def snapshot(root):
    return {str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / "发行 包" / "skills" / installer.SKILL_NAME
        self.source.mkdir(parents=True)
        (self.source / "scripts").mkdir()
        (self.source / "assets").mkdir()
        (self.source / "SKILL.md").write_text("# Installation test fixture\n", encoding="utf-8")
        for name in installer.REQUIRED_SCRIPTS:
            content = '{"fixture":true}\n' if name.endswith(".json") else "# Fixture only\n"
            (self.source / "scripts" / name).write_text(content, encoding="utf-8")
        for name in installer.REQUIRED_ASSETS + installer.CHART_RESOURCES:
            (self.source / "assets" / name).parent.mkdir(parents=True, exist_ok=True)
            (self.source / "assets" / name).write_text('{"fixture":true}\n', encoding="utf-8")
        (self.source / "references").mkdir()
        (self.source / "references" / "额外 说明.md").write_bytes(b"exact bytes\r\n")
        self.destination = self.root / "项目 空间" / ".agents" / "skills" / installer.SKILL_NAME

    def old_installation(self):
        self.destination.mkdir(parents=True)
        (self.destination / "original.txt").write_bytes(b"keep this original\x00\xff")
        return snapshot(self.destination)

    def code_only_release(self, metadata=None):
        metadata = metadata if metadata is not None else {
            "edition": "code-only", "dataset_included": False
        }
        release_root = self.source.parent.parent
        (release_root / "EDITION.json").write_text(json.dumps(metadata), encoding="utf-8")
        (release_root / "NOTICE").write_text("Fixture data notice\n", encoding="utf-8")
        (release_root / "LICENSE").write_text("Fixture license\n", encoding="utf-8")
        for name in installer.REQUIRED_ASSETS:
            (self.source / "assets" / name).unlink()

    def test_install_preserves_complete_tree_and_bytes(self):
        before = snapshot(self.source)
        result = installer.install(self.source, self.destination)
        self.assertEqual(before, snapshot(self.destination))
        self.assertEqual(before, snapshot(self.source))
        self.assertIsNone(result.backup)

    def test_refuses_overwrite_and_keeps_original(self):
        before = self.old_installation()
        with self.assertRaises(installer.InstallError):
            installer.install(self.source, self.destination)
        self.assertEqual(before, snapshot(self.destination))
        self.assertEqual([self.destination], list(self.destination.parent.iterdir()))

    def test_force_backs_up_whole_original_without_merging(self):
        before = self.old_installation()
        result = installer.install(self.source, self.destination, force=True)
        self.assertEqual(before, snapshot(result.backup))
        self.assertEqual(snapshot(self.source), snapshot(self.destination))
        self.assertFalse((self.destination / "original.txt").exists())
        self.assertEqual(self.destination.parent, result.backup.parent)

    def test_copy_failure_preserves_original(self):
        before = self.old_installation()
        with mock.patch.object(installer.shutil, "copytree", side_effect=OSError("copy failed")):
            with self.assertRaises(OSError):
                installer.install(self.source, self.destination, force=True)
        self.assertEqual(before, snapshot(self.destination))
        self.assertEqual([self.destination], list(self.destination.parent.iterdir()))

    def test_replace_failure_restores_original(self):
        before = self.old_installation()
        real_rename = Path.rename

        def fail_new_payload(path, target):
            if path.name == "payload":
                raise OSError("replacement failed")
            return real_rename(path, target)

        with mock.patch.object(Path, "rename", fail_new_payload):
            with self.assertRaises(OSError):
                installer.install(self.source, self.destination, force=True)
        self.assertEqual(before, snapshot(self.destination))
        self.assertEqual([self.destination], list(self.destination.parent.iterdir()))

    def test_failed_restore_preserves_backup_and_reports_path(self):
        before = self.old_installation()
        real_rename = Path.rename

        def fail_payload_and_restore(path, target):
            if path.name == "payload" or ".backup-" in path.name:
                raise OSError("replacement or restoration failed")
            return real_rename(path, target)

        with mock.patch.object(Path, "rename", fail_payload_and_restore):
            with self.assertRaises(installer.InstallError) as raised:
                installer.install(self.source, self.destination, force=True)
        backups = list(self.destination.parent.glob(installer.SKILL_NAME + ".backup-*"))
        self.assertEqual(1, len(backups))
        self.assertEqual(before, snapshot(backups[0]))
        self.assertIn(str(backups[0]), str(raised.exception))

    def test_dry_run_does_not_create_directories(self):
        result = installer.install(self.source, self.destination, dry_run=True)
        self.assertTrue(result.dry_run)
        self.assertFalse(self.destination.parent.exists())

    def test_force_dry_run_does_not_move_original(self):
        before = self.old_installation()
        installer.install(self.source, self.destination, force=True, dry_run=True)
        self.assertEqual(before, snapshot(self.destination))
        self.assertEqual([self.destination], list(self.destination.parent.iterdir()))

    def test_symlink_and_dangling_symlink_are_refused(self):
        protected = self.root / "protected"
        protected.mkdir()
        (protected / "original.txt").write_bytes(b"original")
        before = snapshot(protected)
        self.destination.parent.mkdir(parents=True)
        for target in (protected, self.root / "absent"):
            with self.subTest(target=target):
                try:
                    self.destination.symlink_to(target, target_is_directory=True)
                except OSError as error:
                    self.skipTest("This host does not permit symlink creation: {}".format(error))
                with self.assertRaises(installer.InstallError):
                    installer.install(self.source, self.destination, force=True)
                self.assertTrue(self.destination.is_symlink())
                self.destination.unlink()
        self.assertEqual(before, snapshot(protected))

    def test_overlap_in_each_direction_is_refused(self):
        before = snapshot(self.source)
        for destination in (self.source, self.source / "nested", self.source.parent):
            with self.subTest(destination=destination):
                with self.assertRaises(installer.InstallError):
                    installer.install(self.source, destination, force=True)
        self.assertEqual(before, snapshot(self.source))

    def test_missing_or_invalid_data_cannot_replace_original(self):
        before = self.old_installation()
        data_path = self.source / "assets" / installer.REQUIRED_ASSETS[0]
        data_path.unlink()
        with self.assertRaises(installer.InstallError):
            installer.install(self.source, self.destination, force=True)
        data_path.write_text("not JSON", encoding="utf-8")
        with self.assertRaises(installer.InstallError):
            installer.install(self.source, self.destination, force=True)
        self.assertEqual(before, snapshot(self.destination))

    def test_explicit_code_only_release_installs_without_assets_and_keeps_notices(self):
        self.code_only_release()
        result = installer.install(self.source, self.destination)
        self.assertTrue(result.code_only)
        self.assertFalse((self.destination / "assets" / installer.REQUIRED_ASSETS[0]).exists())
        self.assertTrue((self.destination / "assets" / "chart-template.html").is_file())
        for name in ("EDITION.json", "NOTICE", "LICENSE"):
            self.assertEqual((self.source.parent.parent / name).read_bytes(),
                             (self.destination / name).read_bytes())
        for name, content in snapshot(self.source).items():
            self.assertEqual(content, (self.destination / name).read_bytes())

    def test_code_only_requires_both_metadata_fields(self):
        cases = ({"edition": "code-only"}, {"dataset_included": False},
                 {"edition": "code-only", "dataset_included": True},
                 {"edition": "full", "dataset_included": False})
        self.code_only_release()
        for metadata in cases:
            with self.subTest(metadata=metadata):
                (self.source.parent.parent / "EDITION.json").write_text(
                    json.dumps(metadata), encoding="utf-8"
                )
                with self.assertRaises(installer.InstallError):
                    installer.install(self.source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_code_only_cli_warns_that_query_data_is_not_imported(self):
        self.code_only_release()
        output = io.StringIO()
        with mock.patch.object(installer, "SOURCE", self.source), contextlib.redirect_stdout(output):
            result = installer.main(["--agent", "codex", "--project", str(self.root / "project")])
        self.assertEqual(0, result)
        self.assertIn("数据未导入，不能查询", output.getvalue())

    def test_cli_requires_agent_and_exactly_one_scope(self):
        cases = ([], ["--agent", "codex"], ["--project", str(self.root)],
                 ["--agent", "codex", "--global", "--project", str(self.root)])
        for arguments in cases:
            with self.subTest(arguments=arguments), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    installer.main(arguments)
                self.assertEqual(2, raised.exception.code)

    def test_cli_project_and_global_agent_paths_use_temporary_home(self):
        fake_home = self.root / "temporary-home"
        expected = {
            "codex": (".agents/skills", ".agents/skills"),
            "claude-code": (".claude/skills", ".claude/skills"),
            "cursor": (".cursor/skills", ".cursor/skills"),
            "github-copilot": (".github/skills", ".copilot/skills"),
        }
        with mock.patch.object(installer, "SOURCE", self.source), mock.patch.object(Path, "home", return_value=fake_home):
            for agent, directories in expected.items():
                for global_install in (False, True):
                    with self.subTest(agent=agent, global_install=global_install):
                        project = self.root / ("project-" + agent)
                        arguments = ["--agent", agent]
                        arguments += ["--global"] if global_install else ["--project", str(project)]
                        with contextlib.redirect_stdout(io.StringIO()):
                            self.assertEqual(0, installer.main(arguments))
                        target = ((fake_home if global_install else project)
                                  / directories[int(global_install)] / installer.SKILL_NAME)
                        self.assertEqual(snapshot(self.source), snapshot(target))


if __name__ == "__main__":
    unittest.main(verbosity=2)
