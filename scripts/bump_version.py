#!/usr/bin/env python3
"""Version bump script for murmurai releases.

Usage:
    python scripts/bump_version.py --action rc      # Bump to next RC
    python scripts/bump_version.py --action stable  # Promote RC to stable
"""

import argparse
import re
import sys
from pathlib import Path

PYPROJECT_PATH = Path("pyproject.toml")
INIT_PATH = Path("src/murmurai_server/__init__.py")


def get_current_version() -> str:
    """Read current version from pyproject.toml."""
    content = PYPROJECT_PATH.read_text()
    match = re.search(r'^version = "([^"]+)"', content, re.MULTILINE)
    if not match:
        raise ValueError("Could not find version in pyproject.toml")
    return match.group(1)


def bump_rc(current: str) -> str:
    """Bump to next RC version.

    Examples:
        2.0.0 -> 2.0.1-rc.1
        2.0.1-rc.1 -> 2.0.1-rc.2
        2.0.1-rc.5 -> 2.0.1-rc.6
    """
    if "-rc." in current:
        # Already an RC, bump the RC number
        base, rc_num = current.rsplit("-rc.", 1)
        return f"{base}-rc.{int(rc_num) + 1}"
    else:
        # Stable version, bump patch and start RC.1
        parts = current.split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid version format: {current}")
        major, minor, patch = parts
        return f"{major}.{minor}.{int(patch) + 1}-rc.1"


def promote_stable(current: str) -> str:
    """Promote RC to stable version, or return stable version as-is for initial release.

    Examples:
        2.1.0-rc.5 -> 2.1.0
        1.0.0 -> 1.0.0 (initial release, no change needed)
    """
    if "-rc." not in current:
        # Already stable - allow for initial releases
        print(f"Version {current} is already stable, proceeding with release")
        return current
    return current.split("-rc.")[0]


def update_pyproject(new_version: str) -> None:
    """Update version in pyproject.toml."""
    content = PYPROJECT_PATH.read_text()
    updated = re.sub(
        r'^version = "[^"]+"',
        f'version = "{new_version}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )
    PYPROJECT_PATH.write_text(updated)
    print(f"Updated pyproject.toml: {new_version}")


def update_init(new_version: str) -> None:
    """Update __version__ in __init__.py."""
    content = INIT_PATH.read_text()
    updated = re.sub(
        r'^__version__ = "[^"]+"',
        f'__version__ = "{new_version}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )
    INIT_PATH.write_text(updated)
    print(f"Updated __init__.py: {new_version}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bump version for release")
    parser.add_argument(
        "--action",
        required=True,
        choices=["rc", "stable"],
        help="Release action: 'rc' for release candidate, 'stable' for stable release",
    )
    args = parser.parse_args()

    try:
        current = get_current_version()
        print(f"Current version: {current}")

        if args.action == "rc":
            new_version = bump_rc(current)
        else:  # stable
            new_version = promote_stable(current)

        print(f"New version: {new_version}")

        update_pyproject(new_version)
        update_init(new_version)

        print(f"Successfully bumped version to {new_version}")
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
