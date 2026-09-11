import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def run_script(self, script, *args, cwd):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), *map(str, args)],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"},
            timeout=30,
        )

    def test_scripts_work_from_another_directory_without_changing_state_on_export(self):
        with TemporaryDirectory() as directory:
            state = Path(directory) / "data" / "state.json"
            output = Path(directory) / "exports"
            generated = self.run_script(
                "generate_chats.py",
                "--chats",
                120,
                "--seed",
                42,
                "--start",
                "2026-01-01",
                "--show",
                0,
                "--state",
                state,
                cwd=directory,
            )
            self.assertEqual(generated.returncode, 0, generated.stderr)
            before = state.read_bytes()
            exported = self.run_script(
                "export_examples.py",
                "--state",
                state,
                "--output-dir",
                output,
                "--quiet",
                "--all",
                cwd=directory,
            )
            self.assertEqual(exported.returncode, 0, exported.stderr)
            self.assertEqual(exported.stdout, "")
            self.assertEqual(state.read_bytes(), before)
            self.assertEqual(len(list(output.glob("*.json"))), 53)
            demo = self.run_script(
                "export_examples.py",
                "--state",
                state,
                "--output-dir",
                output,
                "--demo",
                "--quiet",
                cwd=directory,
            )
            self.assertEqual(demo.returncode, 0, demo.stderr)
            self.assertEqual(len(json.loads(state.read_text(encoding="utf-8"))["chats"]), 121)

    def test_invalid_arguments_and_corrupt_state_exit_with_clear_errors(self):
        with TemporaryDirectory() as directory:
            for args in (("--operators", 0), ("--chats", 99), ("--users", -1), ("--show", -1)):
                result = self.run_script("generate_chats.py", *args, cwd=directory)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertNotIn("Traceback", result.stderr)
            state = Path(directory) / "state.json"
            state.write_text("invalid", encoding="utf-8")
            result = self.run_script("export_examples.py", "--state", state, cwd=directory)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(state.read_text(encoding="utf-8"), "invalid")

    def test_export_creates_a_missing_dataset(self):
        with TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            result = self.run_script(
                "export_examples.py",
                "--state",
                state,
                "--output-dir",
                Path(directory) / "exports",
                "--quiet",
                "--seed",
                3,
                cwd=directory,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(json.loads(state.read_text(encoding="utf-8"))["chats"]), 120)
