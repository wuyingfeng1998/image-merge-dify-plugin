#!/usr/bin/env python3
"""Build a self-contained .difypkg that installs without network access.

Every Python dependency (dify_plugin, Pillow and their transitive
dependencies) is downloaded as a Linux x86_64 / CPython 3.12 wheel into
``wheels/`` inside the build directory, and the Dify plugin daemon is pointed
at that local wheelhouse through ``requirements.txt`` and ``[tool.uv]``.

Usage:
    python scripts/build_offline.py --dify /path/to/dify --output dist/image-merge-0.0.2.difypkg
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLATFORMS = (
    "manylinux_2_28_x86_64",
    "manylinux_2_17_x86_64",
    "manylinux2014_x86_64",
)
IGNORE = ("wheels", "__pycache__", ".venv", ".git", "dist", "*.difypkg")


def build(dify: str, output: Path, platforms: tuple[str, ...]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        build_dir = Path(tmp) / "image-merge"
        shutil.copytree(ROOT, build_dir, ignore=shutil.ignore_patterns(*IGNORE))

        download = [
            sys.executable, "-m", "pip", "download",
            "-r", "requirements.txt",
            "-d", "wheels",
            "--python-version", "3.12",
            "--implementation", "cp",
            "--abi", "cp312",
            "--only-binary=:all:",
            "--no-cache-dir",
        ]
        for platform_tag in platforms:
            download += ["--platform", platform_tag]
        print("Downloading wheels:", " ".join(platforms))
        subprocess.run(download, cwd=build_dir, check=True)

        shutil.copy(build_dir / "requirements-offline.txt", build_dir / "requirements.txt")
        pyproject = (build_dir / "pyproject.toml").read_text(encoding="utf-8")
        pyproject += (
            '\n[tool.uv]\n'
            'no-index = true\n'
            'find-links = ["./wheels"]\n'
            'environments = ["sys_platform == \'linux\'"]\n'
            'package = false\n'
        )
        (build_dir / "pyproject.toml").write_text(pyproject, encoding="utf-8")

        output.parent.mkdir(parents=True, exist_ok=True)
        print("Packaging plugin ->", output)
        subprocess.run(
            [dify, "plugin", "package", str(build_dir), "-o", str(output.resolve()), "--max-size", "200"],
            check=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dify", default="dify", help="Path to the Dify plugin CLI")
    parser.add_argument(
        "--output",
        default=str(ROOT.parent / f"image-merge-{ROOT.name}-offline.difypkg"),
        help="Output .difypkg path",
    )
    parser.add_argument(
        "--platform",
        action="append",
        dest="platforms",
        help="Wheel platform tag, repeatable (default: manylinux x86_64 tags)",
    )
    args = parser.parse_args()
    build(args.dify, Path(args.output), tuple(args.platforms or DEFAULT_PLATFORMS))


if __name__ == "__main__":
    main()
