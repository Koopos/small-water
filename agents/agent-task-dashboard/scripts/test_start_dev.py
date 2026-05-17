from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("start_dev.py")
SPEC = importlib.util.spec_from_file_location("start_dev", MODULE_PATH)
assert SPEC and SPEC.loader
start_dev = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = start_dev
SPEC.loader.exec_module(start_dev)


class StartDevScriptTests(unittest.TestCase):
    def test_build_process_specs_starts_next_and_worker(self):
        specs = start_dev.build_process_specs(
            repo_root=Path("/repo"),
            api_base_url="http://127.0.0.1:3000",
            worker_pool="content",
            include_worker=True,
        )

        self.assertEqual([spec["name"] for spec in specs], ["next", "worker-content"])
        self.assertEqual(specs[0]["command"], ["npm", "run", "dev"])
        self.assertEqual(specs[0]["cwd"], Path("/repo"))
        self.assertEqual(specs[1]["command"], [sys.executable, "worker/main.py", "--api-base-url", "http://127.0.0.1:3000", "--worker-pool", "content"])
        self.assertEqual(specs[1]["cwd"], Path("/repo"))

    def test_build_process_specs_can_disable_worker(self):
        specs = start_dev.build_process_specs(
            repo_root=Path("/repo"),
            api_base_url="http://127.0.0.1:3000",
            worker_pool="content",
            include_worker=False,
        )

        self.assertEqual([spec["name"] for spec in specs], ["next"])

    def test_build_process_specs_default_all_expands_to_three_workers(self):
        specs = start_dev.build_process_specs(
            repo_root=Path("/repo"),
            api_base_url="http://127.0.0.1:3000",
            worker_pool="all",
            include_worker=True,
        )

        self.assertEqual([spec["name"] for spec in specs], ["next", "worker-code", "worker-image", "worker-content"])
        self.assertEqual([spec["command"][-1] for spec in specs[1:]], ["code", "image", "content"])

    def test_state_path_is_under_run_directory(self):
        self.assertEqual(start_dev.default_state_path(Path("/repo")), Path("/repo/.run/dev-launcher.json"))

    def test_supervise_once_restarts_dead_worker(self):
        class FakeProcess:
            def __init__(self, pid: int, polls: list[int | None]):
                self.pid = pid
                self._polls = polls
                self.poll_calls = 0

            def poll(self):
                value = self._polls[min(self.poll_calls, len(self._polls) - 1)]
                self.poll_calls += 1
                return value

        launched = []
        next_proc = FakeProcess(101, [None, None])
        worker_proc = FakeProcess(202, [1, 1])
        replacement_worker = FakeProcess(303, [None])
        processes = {"next": next_proc, "worker-content": worker_proc}
        specs = {
            "next": {"name": "next", "command": ["npm", "run", "dev"], "cwd": Path("/repo")},
            "worker-content": {"name": "worker-content", "command": [sys.executable, "worker/main.py", "--worker-pool", "content"], "cwd": Path("/repo")},
        }

        def fake_launch(command, cwd, env):
            launched.append(command)
            if len(launched) == 1:
                return replacement_worker
            raise AssertionError("unexpected extra launch")

        with patch.object(start_dev, "launch_process", side_effect=fake_launch), \
            patch.object(start_dev, "write_state", return_value=None), \
            patch.object(start_dev, "terminate_pid", return_value=True), \
            patch.object(start_dev.time, "sleep", side_effect=KeyboardInterrupt), \
            patch.object(start_dev, "wait_for_port", return_value=True):
            with self.assertRaises(KeyboardInterrupt):
                start_dev.supervise_forever(
                    processes=processes,
                    process_specs=specs,
                    env={"PORT": "3000"},
                    state_path=Path("/repo/.run/dev-launcher.json"),
                    repo_root=Path("/repo"),
                    api_base_url="http://127.0.0.1:3000",
                    worker_pool="content",
                    include_worker=True,
                    next_port=3000,
                )

        self.assertEqual(replacement_worker.pid, 303)
        self.assertEqual(len(launched), 1)

    def test_start_project_launches_next_before_worker(self):
        events: list[str] = []

        class FakeProcess:
            def __init__(self, pid: int):
                self.pid = pid

            def poll(self):
                return None

        def fake_launch(command, cwd, env):
            events.append(command[0])
            return FakeProcess(100 + len(events))

        with patch.object(start_dev, "launch_process", side_effect=fake_launch), \
            patch.object(start_dev, "wait_for_port", return_value=True), \
            patch.object(start_dev, "write_state", return_value=None), \
            patch.object(start_dev, "read_state", return_value=None), \
            patch.object(start_dev, "terminate_pid", return_value=True), \
            patch.object(start_dev.time, "sleep", side_effect=KeyboardInterrupt):
            exit_code = start_dev.start_project(
                repo_root=Path("/repo"),
                api_base_url="http://127.0.0.1:3000",
                worker_pool="content",
                include_worker=True,
                restart=False,
                next_port=3000,
            )

        self.assertEqual(exit_code, 130)
        self.assertEqual(events, ["npm", sys.executable])


if __name__ == "__main__":
    unittest.main()
