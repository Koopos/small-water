import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch


MODULE_PATH = Path(__file__).with_name("main.py")
SPEC = importlib.util.spec_from_file_location("worker_main", MODULE_PATH)
worker_main = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
import sys
sys.modules[SPEC.name] = worker_main
SPEC.loader.exec_module(worker_main)


class WorkerMainTests(unittest.TestCase):
    def test_build_content_output_dating_post(self):
        task = {
            "id": "task-1",
            "type": "agent-dating-post",
            "title": "成年人突然不联系，其实就是答案",
            "description": "写一个 6 页相亲图文，语气扎心但别太刻薄",
            "input": {},
        }

        output = worker_main.build_content_output(task)
        self.assertIn("pages", output)
        self.assertEqual(output["taskType"], "agent-dating-post")
        self.assertGreaterEqual(len(output["pages"]), 4)
        self.assertIn("summary", output)

    def test_write_placeholder_png_creates_valid_png(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "preview.png"
            worker_main.write_placeholder_png(output_path, "hello world")
            data = output_path.read_bytes()
            self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertGreater(len(data), 100)

    def test_build_image_output_returns_preview_url(self):
        task = {
            "id": "task-2",
            "type": "agent-image",
            "title": "封面图",
            "description": "赛博风格的封面图",
            "input": {"aspect_ratio": "square", "style": "cyberpunk"},
            "project": {"id": "project-1"},
        }

        def fake_run(command, *, cwd, env, stdin_text):
            if command[0] == "codex" and command[1].startswith("$imagegen "):
                return type("CompletedProcess", (), {"returncode": 1, "stdout": "", "stderr": "codex unavailable"})()
            raise AssertionError(f"unexpected command: {command}")

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(worker_main, "run_external_command", Mock(side_effect=fake_run)):
            output = worker_main.build_image_output(task, Path(tmpdir))
            self.assertEqual(output["taskType"], "agent-image")
            self.assertIn("preview_urls", output)
            self.assertTrue(output["preview_urls"])
            self.assertTrue(output["preview_urls"][0].endswith(".png"))

    def test_build_image_output_uses_codex_imagegen_result(self):
        task = {
            "id": "task-2b",
            "type": "agent-image",
            "title": "未来感产品海报",
            "description": "根据详细需求生成一张科技感强的宣传图",
            "input": {
                "aspect_ratio": "16:9",
                "subject": "AI 终端",
                "scene": "霓虹城市夜景",
                "style": "赛博朋克",
                "mood": "高级、冷峻、未来感",
                "lighting": "蓝紫霓虹光",
                "palette": ["#0B1020", "#2D6BFF", "#F97316"],
                "copy": "今晚发布",
            },
            "project": {"id": "project-1"},
        }

        def fake_run(command, *, cwd, env, stdin_text):
            if command[0] == "codex" and command[1].startswith("$imagegen "):
                worker_main.write_placeholder_png(Path(cwd) / "codex-image.png", "codex generated")
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "generated", "stderr": ""})()
            raise AssertionError(f"unexpected command: {command}")

        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(worker_main.os.environ, {"IMAGE_TASK_COMMAND": ""}, clear=False), patch.object(
            worker_main,
            "run_external_command",
            Mock(side_effect=fake_run),
        ):
            output = worker_main.build_image_output(task, Path(tmpdir))
            self.assertTrue(output["generated_with_codex"])
            self.assertEqual(output["codex_command"][0], "codex")
            self.assertTrue(output["codex_command"][1].startswith("$imagegen "))
            self.assertIn("preview_urls", output)
            self.assertTrue(output["preview_urls"][0].endswith(".png"))
            self.assertTrue((Path(tmpdir) / "preview.png").exists())
            self.assertTrue((Path(tmpdir) / "metadata.json").exists())

    def test_build_image_output_falls_back_when_codex_returns_invalid_json(self):
        task = {
            "id": "task-2c",
            "type": "agent-image",
            "title": "封面图",
            "description": "赛博风格的封面图",
            "input": {"aspect_ratio": "square", "style": "cyberpunk"},
            "project": {"id": "project-1"},
        }

        def fake_run(command, *, cwd, env, stdin_text):
            if command[0] == "codex" and command[1].startswith("$imagegen "):
                return type("CompletedProcess", (), {"returncode": 1, "stdout": "", "stderr": "codex failed"})()
            raise AssertionError(f"unexpected command: {command}")

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(worker_main, "run_external_command", Mock(side_effect=fake_run)):
            output = worker_main.build_image_output(task, Path(tmpdir))
            self.assertFalse(output["generated_with_codex"])
            self.assertIn("Codex $imagegen 未生成图片", output["summary"])
            self.assertTrue((Path(tmpdir) / "preview.png").exists())

    def test_build_code_output_clones_github_reference_when_local_path_missing(self):
        task = {
            "id": "task-4",
            "type": "agent-dev",
            "title": "修复登录按钮",
            "description": "检查组件和测试，修复按钮点击无效的问题",
            "input": {"references": ["https://github.com/Koopos/baby"]},
            "project": {"repo": "Koopos/baby", "localPath": None, "defaultBranch": "main"},
        }

        pr_state = {"created": False}

        def fake_run(command, *, cwd, env, stdin_text):
            if command[:2] == ["git", "fetch"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if command[:3] == ["git", "checkout", "main"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if command[:2] == ["git", "pull"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if command[:3] == ["git", "checkout", "-B"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if command[:3] == ["git", "remote", "get-url"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "git@github.com:Koopos/baby.git\n", "stderr": ""})()
            if command[:2] == ["git", "status"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if command[:2] == ["git", "add"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if command[:2] == ["git", "reset"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if command[:3] == ["git", "diff", "--cached"]:
                return type("CompletedProcess", (), {"returncode": 1, "stdout": "src/app/page.tsx\n", "stderr": ""})()
            if command[:2] == ["git", "commit"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "[main abc1234] feat(agent-dev): 修复登录按钮\n", "stderr": ""})()
            if command[:2] == ["git", "rev-parse"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "abc1234\n", "stderr": ""})()
            if command[:2] == ["git", "push"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "branch pushed\n", "stderr": ""})()
            if command[:3] == ["gh", "pr", "list"]:
                if pr_state["created"]:
                    return type("CompletedProcess", (), {"returncode": 0, "stdout": '[{"url":"https://github.com/Koopos/baby/pull/42","number":42,"state":"OPEN"}]', "stderr": ""})()
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "[]", "stderr": ""})()
            if command[:3] == ["gh", "pr", "create"]:
                pr_state["created"] = True
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "https://github.com/Koopos/baby/pull/42\n", "stderr": ""})()
            if command[:2] == ["hermes", "chat"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": '{"summary": "done"}', "stderr": "session_id: 20260517_175416_105ef3"})()
            raise AssertionError(f"unexpected command: {command}")

        with tempfile.TemporaryDirectory() as tmpdir:
            checkout_dir = Path(tmpdir) / ".run" / "code-repos" / "task-4"
            artifact_dir = Path(tmpdir) / "artifacts" / "task-4"
            with patch.dict(worker_main.os.environ, {"CODE_TASK_COMMAND": "", "AGENT_DEV_COMMAND": ""}, clear=False), patch.object(
                worker_main,
                "worker_repo_root",
                return_value=Path(tmpdir),
            ), patch.object(
                worker_main,
                "resolve_artifact_root",
                return_value=artifact_dir,
            ), patch.object(
                worker_main,
                "clone_github_repo",
                Mock(return_value=checkout_dir),
            ) as clone_github_repo, patch.object(
                worker_main,
                "run_external_command",
                Mock(side_effect=fake_run),
            ) as run_external_command:
                output = worker_main.build_code_output(task)

        self.assertEqual(output["summary"], "代码任务已提交到新的 Git 分支、推送到 GitHub，并创建 PR。")
        self.assertTrue(output["branch"].startswith("agent-dev/task-4-"))
        self.assertEqual(output["github_commit_sha"], "abc1234")
        self.assertEqual(output["pr_url"], "https://github.com/Koopos/baby/pull/42")
        clone_github_repo.assert_called_once()
        self.assertEqual(clone_github_repo.call_args.args[0], "https://github.com/Koopos/baby.git")
        self.assertEqual(clone_github_repo.call_args.args[1], checkout_dir)
        hermes_call = next(call for call in run_external_command.call_args_list if call.args[0][:2] == ["hermes", "chat"])
        self.assertEqual(hermes_call.kwargs["cwd"], str(checkout_dir))
        self.assertIn("code-repos/task-4", hermes_call.kwargs["cwd"])
        self.assertNotIn("stderr", output)
        gh_create_call = next(call for call in run_external_command.call_args_list if call.args[0][:3] == ["gh", "pr", "create"])
        self.assertIn("--head", gh_create_call.args[0])
        self.assertIn("--base", gh_create_call.args[0])



    def test_build_code_output_defaults_to_hermes_command(self):
        task = {
            "id": "task-3",
            "type": "agent-dev",
            "title": "修复登录按钮",
            "description": "检查组件和测试，修复按钮点击无效的问题",
            "input": {"references": ["src/app/page.tsx"]},
            "project": {"localPath": "/repo/app", "defaultBranch": "main"},
        }

        pr_state = {"created": False}

        def fake_run(command, *, cwd, env, stdin_text):
            if command[:2] == ["git", "fetch"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if command[:3] == ["git", "checkout", "main"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if command[:2] == ["git", "pull"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if command[:3] == ["git", "checkout", "-B"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if command[:3] == ["git", "remote", "get-url"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "git@github.com:Koopos/baby.git\n", "stderr": ""})()
            if command[:2] == ["git", "status"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if command[:2] == ["git", "add"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if command[:2] == ["git", "reset"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if command[:3] == ["git", "diff", "--cached"]:
                return type("CompletedProcess", (), {"returncode": 1, "stdout": "src/app/page.tsx\n", "stderr": ""})()
            if command[:2] == ["git", "commit"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "[main abc1234] feat(agent-dev): 修复登录按钮\n", "stderr": ""})()
            if command[:2] == ["git", "rev-parse"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "abc1234\n", "stderr": ""})()
            if command[:2] == ["git", "push"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "branch pushed\n", "stderr": ""})()
            if command[:3] == ["gh", "pr", "list"]:
                if pr_state["created"]:
                    return type("CompletedProcess", (), {"returncode": 0, "stdout": '[{"url":"https://github.com/Koopos/baby/pull/43","number":43,"state":"OPEN"}]', "stderr": ""})()
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "[]", "stderr": ""})()
            if command[:3] == ["gh", "pr", "create"]:
                pr_state["created"] = True
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "https://github.com/Koopos/baby/pull/43\n", "stderr": ""})()
            if command[:2] == ["hermes", "chat"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": '{"summary": "done"}', "stderr": "session_id: 20260517_174718_e53a99"})()
            raise AssertionError(f"unexpected command: {command}")

        with patch.dict(worker_main.os.environ, {"CODE_TASK_COMMAND": "", "AGENT_DEV_COMMAND": ""}, clear=False), patch.object(
            worker_main,
            "run_external_command",
            Mock(side_effect=fake_run),
        ) as run_external_command, patch.object(worker_main, "resolve_repo_path", return_value=("/repo/app", None)) as resolve_repo_path, patch.object(worker_main, "clone_github_repo") as clone_github_repo:
            output = worker_main.build_code_output(task)

        self.assertEqual(output["summary"], "代码任务已提交到新的 Git 分支、推送到 GitHub，并创建 PR。")
        self.assertNotIn("stderr", output)
        self.assertTrue(output["branch"].startswith("agent-dev/task-3-"))
        self.assertEqual(output["github_commit_sha"], "abc1234")
        self.assertEqual(output["pr_url"], "https://github.com/Koopos/baby/pull/43")
        clone_github_repo.assert_not_called()
        self.assertGreaterEqual(run_external_command.call_count, 1)
        hermes_call = next(call for call in run_external_command.call_args_list if call.args[0][:2] == ["hermes", "chat"])
        command = hermes_call.args[0]
        self.assertIsInstance(command, list)
        self.assertEqual(command[:4], ["hermes", "chat", "-Q", "-q"])
        self.assertIn("-t", command)
        self.assertIn("terminal,file", command)
        self.assertIn("--yolo", command)
        self.assertIn("修复登录按钮", command[4])
        self.assertEqual(hermes_call.kwargs["cwd"], "/repo/app")
        gh_create_call = next(call for call in run_external_command.call_args_list if call.args[0][:3] == ["gh", "pr", "create"])
        self.assertIn("--head", gh_create_call.args[0])
        self.assertIn("--base", gh_create_call.args[0])

    def test_build_code_output_surfaces_context_when_hermes_fails(self):
        task = {
            "id": "task-5",
            "type": "agent-dev",
            "title": "修复登录按钮",
            "description": "检查组件和测试，修复按钮点击无效的问题",
            "input": {"references": ["src/app/page.tsx"]},
            "project": {"localPath": "/repo/app", "defaultBranch": "main"},
        }

        def fake_run(command, *, cwd, env, stdin_text):
            if command[:2] == ["git", "fetch"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if command[:3] == ["git", "checkout", "main"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if command[:2] == ["git", "pull"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if command[:3] == ["git", "checkout", "-B"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if command[:2] == ["git", "status"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if command[:2] == ["git", "add"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if command[:2] == ["git", "reset"]:
                return type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if command[:2] == ["hermes", "chat"]:
                return type("CompletedProcess", (), {"returncode": 1, "stdout": "", "stderr": "session_id: 20260517_205107_7c88b2"})()
            raise AssertionError(f"unexpected command: {command}")

        with patch.dict(worker_main.os.environ, {"CODE_TASK_COMMAND": "", "AGENT_DEV_COMMAND": ""}, clear=False), patch.object(
            worker_main,
            "run_external_command",
            Mock(side_effect=fake_run),
        ), patch.object(worker_main, "resolve_repo_path", return_value=("/repo/app", None)):
            with self.assertRaises(worker_main.WorkerError) as ctx:
                worker_main.build_code_output(task)

        message = str(ctx.exception)
        self.assertIn("hermes exited with code 1", message)
        self.assertIn("session_id: 20260517_205107_7c88b2", message)
        self.assertIn("repo_path: /repo/app", message)
        self.assertIn("branch: agent-dev/task-5-", message)

    def test_clone_github_repo_retries_transient_tls_errors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            checkout_dir = Path(tmpdir) / "repo"
            transient = type("CompletedProcess", (), {"returncode": 1, "stdout": "", "stderr": "Cloning into ...\n fatal: unable to access 'https://github.com/Koopos/baby.git/': GnuTLS recv error (-110): The TLS connection was non-properly terminated."})()
            success = type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": "Cloning into ..."})()

            with patch.object(worker_main, "run_external_command", side_effect=[transient, success]) as run_external_command:
                result = worker_main.clone_github_repo("https://github.com/Koopos/baby.git", checkout_dir)

        self.assertEqual(result, checkout_dir)
        self.assertEqual(run_external_command.call_count, 2)
        self.assertEqual(run_external_command.call_args.kwargs["cwd"], checkout_dir.parent)
        self.assertEqual(run_external_command.call_args.kwargs["env"]["GIT_HTTP_VERSION"], "HTTP/1.1")
