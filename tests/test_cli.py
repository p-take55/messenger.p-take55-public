from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def run_cli(data_dir: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "messenger_local_runner.cli",
            "--data-dir",
            str(data_dir),
            *args,
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


class CliTest(unittest.TestCase):
    def test_status_before_init_returns_json_next_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli(pathlib.Path(tmp), "status", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIs(payload["ok"], True)
            self.assertIs(payload["sqlite"]["ok"], False)
            self.assertEqual(payload["next_actions"][0]["command"], "reply-drafter init")

    def test_init_creates_sqlite_and_status_reports_queues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = pathlib.Path(tmp)
            init = run_cli(data_dir, "init", "--json")
            self.assertEqual(init.returncode, 0, init.stderr)
            init_payload = json.loads(init.stdout)
            self.assertIs(init_payload["sqlite"]["ok"], True)
            self.assertTrue((data_dir / "reply-drafter.sqlite").exists())

            status = run_cli(data_dir, "status", "--json")
            self.assertEqual(status.returncode, 0, status.stderr)
            payload = json.loads(status.stdout)
            self.assertIs(payload["sqlite"]["ok"], True)
            self.assertEqual(payload["connectors"]["slack"]["state"], "disabled")
            self.assertEqual(payload["queues"]["received"], 0)

    def test_slack_catch_up_requires_saved_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = pathlib.Path(tmp)
            init = run_cli(data_dir, "init", "--json")
            self.assertEqual(init.returncode, 0, init.stderr)

            result = run_cli(
                data_dir,
                "catch-up",
                "--json",
                "--provider",
                "slack",
                "--channel-limit",
                "1",
                "--per-channel",
                "1",
            )

            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertIs(payload["ok"], False)
            self.assertEqual(payload["provider"], "slack")
            self.assertEqual(payload["error"], "missing_slack_user_token")


if __name__ == "__main__":
    unittest.main()
