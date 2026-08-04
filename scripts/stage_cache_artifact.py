from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


CACHE_PATHS = (
    "cache/dcf",
    "cache/history/dcf",
    "cache/reports/failures",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage only cache files changed by one update shard",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    return parser.parse_args()


def _git_paths(repo_root: Path, arguments: list[str]) -> set[Path]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *arguments],
        check=True,
        stdout=subprocess.PIPE,
    )
    return {
        Path(raw_path.decode("utf-8"))
        for raw_path in result.stdout.split(b"\0")
        if raw_path
    }


def changed_cache_paths(repo_root: Path) -> list[Path]:
    modified = _git_paths(
        repo_root,
        [
            "diff",
            "--name-only",
            "-z",
            "--diff-filter=ACMRTUXB",
            "HEAD",
            "--",
            *CACHE_PATHS,
        ],
    )
    untracked = _git_paths(
        repo_root,
        [
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            *CACHE_PATHS,
        ],
    )
    return sorted(modified | untracked)


def stage_cache_artifact(
    repo_root: Path,
    output_dir: Path,
    shard_index: int,
) -> list[Path]:
    repo_root = repo_root.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    staged: list[Path] = []

    for relative_path in changed_cache_paths(repo_root):
        source_path = (repo_root / relative_path).resolve()
        try:
            source_path.relative_to(repo_root)
        except ValueError as error:
            raise ValueError(
                f"Cache path escapes repository: {relative_path}"
            ) from error
        if not source_path.is_file():
            continue
        try:
            with source_path.open(encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(
                f"Invalid JSON in shard artifact: {relative_path}"
            ) from error
        if not isinstance(payload, dict):
            raise ValueError(
                f"Shard artifact JSON must contain an object: {relative_path}"
            )

        destination = output_dir / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        staged.append(relative_path)

    metadata_path = output_dir / f"cache-shard-{shard_index}.json"
    metadata_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "shard_index": shard_index,
                "file_count": len(staged),
                "files": [str(path) for path in staged],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return staged


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    staged = stage_cache_artifact(repo_root, args.output, args.shard_index)
    print(f"Staged {len(staged)} changed cache file(s) for shard {args.shard_index}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
