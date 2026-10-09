#!/usr/bin/env python3
"""Install the bundled skill offline with Python 3.9+ and the standard library."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Optional, Sequence
import uuid


SKILL_NAME = "nba-take-home-pay"
SOURCE = Path(__file__).resolve().parent / "skills" / SKILL_NAME
AGENT_DIRECTORIES = {
    "codex": (".agents/skills", ".agents/skills"),
    "claude-code": (".claude/skills", ".claude/skills"),
    "cursor": (".cursor/skills", ".cursor/skills"),
    "github-copilot": (".github/skills", ".copilot/skills"),
}
REQUIRED_SCRIPTS = (
    "take_home.py", "build_estimates.py", "estimate.py", "duty_days.py",
    "state_labels.py", "player_names.py", "player_ages.py", "data_status.py", "escrow.py", "tax_east.py", "tax_west.py",
    "tax_federal.py", "query_cache.py", "lookup_2026_27.py",
    "tax-east.json", "tax-west.json", "tax-federal-crossborder.json", "escrow-rules.json",
)
REQUIRED_ASSETS = (
    "salaries-2025-26.json", "salaries-2026-27.json",
    "schedule-2025-26.json", "schedule-2026-27.json",
    "coverage-2025-26.json", "coverage-2026-27.json",
    "player-tax-profiles-2026-27.json", "net-estimates-2026-27.json",
    "player-name-index-2026-27.json", "player-birthdates-2026-27.json",
)


class InstallError(Exception):
    """An installation could not be completed safely."""


@dataclass(frozen=True)
class InstallResult:
    destination: Path
    backup: Optional[Path] = None
    dry_run: bool = False
    code_only: bool = False


def release_metadata(source: Path):
    """Only an explicit release declaration can waive bundled data checks."""
    release_root = source.parent.parent
    edition_path = release_root / "EDITION.json"
    metadata_files = []
    code_only = False
    for name in ("EDITION.json", "NOTICE", "LICENSE"):
        path = release_root / name
        if path.is_symlink():
            raise InstallError("发行元数据不能是符号链接：{}".format(path))
        if path.exists():
            if not path.is_file():
                raise InstallError("发行元数据必须是文件：{}".format(path))
            metadata_files.append(path)
    if edition_path.exists():
        try:
            metadata = json.loads(edition_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as error:
            raise InstallError("发行版 EDITION.json 无法读取。") from error
        if not isinstance(metadata, dict):
            raise InstallError("发行版 EDITION.json 必须是 JSON 对象。")
        code_only = (metadata.get("edition") == "code-only"
                     and metadata.get("dataset_included") is False)
    return code_only, metadata_files


def validate_source(source: Path, *, code_only: bool = False) -> None:
    """Check the complete runtime payload without running the tax engine."""
    if source.is_symlink() or not source.is_dir():
        raise InstallError("技能源目录不存在或是符号链接：{}".format(source))
    for path in source.rglob("*"):
        if path.is_symlink():
            raise InstallError("技能源目录含符号链接，无法保证完整离线复制：{}".format(path))
    for name in (("scripts",) if code_only else ("scripts", "assets")):
        if not (source / name).is_dir():
            raise InstallError("技能包缺少目录：{}".format(name))
    required = [source / "SKILL.md"]
    required.extend(source / "scripts" / name for name in REQUIRED_SCRIPTS)
    if not code_only:
        required.extend(source / "assets" / name for name in REQUIRED_ASSETS)
    for path in required:
        if not path.is_file() or path.stat().st_size == 0:
            raise InstallError("技能包缺少文件或文件为空：{}".format(path.relative_to(source)))
        if path.suffix == ".json":
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, ValueError) as error:
                raise InstallError("技能包 JSON 无法读取：{}".format(path.relative_to(source))) from error
            if not isinstance(value, dict):
                raise InstallError("技能包 JSON 必须是对象：{}".format(path.relative_to(source)))


def destination_for(agent: str, project: Optional[Path], global_install: bool) -> Path:
    if (project is None) != global_install:
        raise InstallError("必须且只能指定 --project PATH 或 --global。")
    project_directory, global_directory = AGENT_DIRECTORIES[agent]
    base = Path.home() if global_install else project.expanduser()
    directory = global_directory if global_install else project_directory
    return base / directory / SKILL_NAME


def validate_destination(source: Path, destination: Path, force: bool) -> Path:
    # Check before resolve(): resolving would hide a dangling or existing link.
    if destination.is_symlink():
        raise InstallError("拒绝安装到符号链接：{}".format(destination))
    source = source.resolve()
    destination = destination.resolve()
    if (source == destination or source in destination.parents
            or destination in source.parents):
        raise InstallError("源目录与安装目录不能重叠：{}".format(destination))
    if destination.exists():
        if not destination.is_dir():
            raise InstallError("安装位置已存在非目录文件：{}".format(destination))
        if not force:
            raise InstallError("技能已存在；使用 --force 备份后替换：{}".format(destination))
    return destination


def backup_path(destination: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    while True:
        candidate = destination.with_name(
            destination.name + ".backup-" + stamp + "-" + uuid.uuid4().hex[:8]
        )
        if not os.path.lexists(str(candidate)):
            return candidate


def install(source: Path, destination: Path, *, force: bool = False,
            dry_run: bool = False) -> InstallResult:
    source = Path(source).expanduser()
    destination = Path(destination).expanduser()
    code_only, metadata_files = release_metadata(source)
    validate_source(source, code_only=code_only)
    source = source.resolve()
    # Keep the un-resolved spelling for the second symlink check before commit.
    requested_destination = destination
    destination = validate_destination(source, destination, force)
    if dry_run:
        return InstallResult(destination=destination, dry_run=True, code_only=code_only)

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(tempfile.mkdtemp(
        prefix="." + SKILL_NAME + ".install-", dir=str(destination.parent)
    ))
    staged = staging_root / "payload"
    backup = None
    try:
        shutil.copytree(source, staged)
        for metadata_path in metadata_files:
            shutil.copy2(metadata_path, staged / metadata_path.name)
        validate_source(staged, code_only=code_only)
        current_destination = validate_destination(source, requested_destination, force)
        if current_destination != destination:
            raise InstallError("复制期间安装目录的实际路径发生变化；已取消安装。")
        if destination.exists():
            backup = backup_path(destination)
            destination.rename(backup)
        try:
            staged.rename(destination)
        except BaseException as error:
            if backup is not None:
                if os.path.lexists(str(destination)):
                    raise InstallError(
                        "替换失败且目标位置被占用；旧安装完整保留于：{}".format(backup)
                    ) from error
                try:
                    backup.rename(destination)
                except OSError as restore_error:
                    raise InstallError(
                        "替换和自动恢复失败；旧安装完整保留于：{}；恢复错误：{}".format(
                            backup, restore_error
                        )
                    ) from error
            raise
    finally:
        # Only remove the private staging tree, never the old or installed tree.
        shutil.rmtree(staging_root, ignore_errors=True)
    return InstallResult(destination=destination, backup=backup, code_only=code_only)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="离线安装 NBA Take-Home Pay 技能。")
    parser.add_argument("--agent", required=True, choices=tuple(AGENT_DIRECTORIES))
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--project", type=Path, metavar="PATH", help="安装到指定项目目录。")
    scope.add_argument("--global", dest="global_install", action="store_true",
                       help="安装到当前用户的个人技能目录。")
    parser.add_argument("--dry-run", action="store_true", help="检查并显示路径，不写入文件。")
    parser.add_argument("--force", action="store_true", help="完整备份已有技能后替换。")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 9):
        parser.error("需要 Python 3.9 或更新版本。")
    try:
        destination = destination_for(args.agent, args.project, args.global_install)
        result = install(SOURCE, destination, force=args.force, dry_run=args.dry_run)
    except (InstallError, OSError) as error:
        print("安装失败：{}".format(error), file=sys.stderr)
        return 1
    if result.dry_run:
        print("检查通过，安装目标：{}".format(result.destination))
        print("预览模式，未写入任何文件。")
    else:
        print("已安装到：{}".format(result.destination))
        if result.backup is not None:
            print("旧安装备份：{}".format(result.backup))
        print("请重新开启 Agent 会话，让宿主发现已安装的 nba-take-home-pay 技能。")
    if result.code_only:
        print("本发行版不附带数据；数据未导入，不能查询。请按发行包 README 导入有权使用的数据。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
