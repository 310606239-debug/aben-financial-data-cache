from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.stage_cache_artifact import stage_cache_artifact


class StageCacheArtifactTests(unittest.TestCase):
    def initialize_repo(self, root: Path) -> None:
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=root,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Cache Test"],
            cwd=root,
            check=True,
        )

    def write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_stages_only_changed_and_untracked_cache_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            self.initialize_repo(root)
            current = root / "cache" / "dcf" / "AAPL.json"
            unchanged = root / "cache" / "dcf" / "TSLA.json"
            self.write_json(current, {"version": 1})
            self.write_json(unchanged, {"version": 1})
            subprocess.run(["git", "add", "cache"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "baseline"], cwd=root, check=True)

            self.write_json(current, {"version": 2})
            history = root / "cache" / "history" / "dcf" / "AAPL" / "snapshot.json"
            failure = root / "cache" / "reports" / "failures" / "shard-3.json"
            self.write_json(history, {"version": 1})
            self.write_json(failure, {"failures": {}})
            output = root / "artifact"

            staged = stage_cache_artifact(root, output, 3)

            self.assertEqual(
                staged,
                [
                    Path("cache/dcf/AAPL.json"),
                    Path("cache/history/dcf/AAPL/snapshot.json"),
                    Path("cache/reports/failures/shard-3.json"),
                ],
            )
            self.assertTrue((output / "cache" / "dcf" / "AAPL.json").exists())
            self.assertFalse((output / "cache" / "dcf" / "TSLA.json").exists())
            metadata = json.loads((output / "cache-shard-3.json").read_text())
            self.assertEqual(metadata["file_count"], 3)

    def test_rejects_invalid_json_before_upload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            self.initialize_repo(root)
            cache_path = root / "cache" / "dcf" / "AAPL.json"
            self.write_json(cache_path, {"version": 1})
            subprocess.run(["git", "add", "cache"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "baseline"], cwd=root, check=True)
            cache_path.write_text("{", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "cache/dcf/AAPL.json"):
                stage_cache_artifact(root, root / "artifact", 0)


if __name__ == "__main__":
    unittest.main()
