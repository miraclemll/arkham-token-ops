#!/usr/bin/env python3
"""Install the bundled arkham-token-ops skill into a Codex/OpenClaw skills directory."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


DEFAULT_SKILL_NAME = "arkham-token-ops"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_dest_root() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home).expanduser() / "skills"
    return Path.home() / ".codex" / "skills"


def source_skill_dir(skill_name: str) -> Path:
    return repo_root() / "skills" / skill_name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install the bundled arkham-token-ops skill into Codex/OpenClaw."
    )
    parser.add_argument(
        "--skill-name",
        default=DEFAULT_SKILL_NAME,
        help=f"Skill directory name under ./skills (default: {DEFAULT_SKILL_NAME}).",
    )
    parser.add_argument(
        "--dest-root",
        default=str(default_dest_root()),
        help="Destination skills root directory (default: $CODEX_HOME/skills or ~/.codex/skills).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing installed skill with the same name.",
    )
    parser.add_argument(
        "--link",
        action="store_true",
        help="Create a symlink instead of copying files. Useful for development.",
    )
    return parser.parse_args()


def ensure_source_exists(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"Skill source not found: {path}")
    if not (path / "SKILL.md").exists():
        raise SystemExit(f"SKILL.md not found in source directory: {path}")


def remove_existing(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    shutil.rmtree(path)


def install_skill(src: Path, dest: Path, *, force: bool, link: bool) -> None:
    if dest.exists() or dest.is_symlink():
        if not force:
            raise SystemExit(
                f"Destination already exists: {dest}\n"
                "Use --force to replace the existing installation."
            )
        remove_existing(dest)

    dest.parent.mkdir(parents=True, exist_ok=True)

    if link:
        dest.symlink_to(src, target_is_directory=True)
        return

    shutil.copytree(src, dest)


def main() -> int:
    args = parse_args()
    src = source_skill_dir(args.skill_name)
    dest_root = Path(args.dest_root).expanduser()
    dest = dest_root / args.skill_name

    ensure_source_exists(src)
    install_skill(src, dest, force=args.force, link=args.link)

    mode = "symlinked" if args.link else "installed"
    print(f"{args.skill_name} {mode} at: {dest}")
    print("Restart Codex/OpenClaw to pick up the new skill.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
