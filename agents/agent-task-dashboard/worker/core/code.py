from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any, Callable

from .common import WorkerError, pretty_json, safe_text, task_input
from .content import build_content_output, build_image_prompt
from .fs import public_url_for, resolve_artifact_root, write_text
from .image import build_image_output
from .process import run_external_command as _run_external_command
from .repo import clone_github_repo, github_clone_url, is_transient_git_clone_error, resolve_repo_path, worker_repo_root


def run_external_command(command: str | list[str], *, cwd: str | None, env: dict[str, str], stdin_text: str):
    from worker import main as worker_main

    if hasattr(worker_main, "run_external_command") and worker_main.run_external_command is not run_external_command:
        return worker_main.run_external_command(command, cwd=cwd, env=env, stdin_text=stdin_text)
    return _run_external_command(command, cwd=cwd, env=env, stdin_text=stdin_text)

def maybe_parse_stdout(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {"result": parsed}
    except json.JSONDecodeError:
        return {"summary": text}

def normalize_success_stderr(stderr: str) -> str:
    text = stderr.strip()
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) == 1 and lines[0].startswith("session_id:"):
        return ""
    return text

def extract_session_id(text: str) -> str | None:
    match = re.search(r"session_id:\s*([A-Za-z0-9_\-]+)", text)
    return match.group(1) if match else None

def format_command_failure(
    *,
    command: str | list[str],
    cwd: str | None,
    result: subprocess.CompletedProcess[str],
    repo_path: str,
    repo_source: str | None,
    repo_full_name: str,
    branch_name: str,
) -> str:
    label = command[0] if isinstance(command, list) and command else (command.split()[0] if isinstance(command, str) and command.strip() else "command")
    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    session_id = extract_session_id(stderr) or extract_session_id(stdout)
    cleaned_stderr = normalize_success_stderr(stderr)
    parts = [f"{label} exited with code {result.returncode}"]
    if session_id:
        parts.append(f"session_id: {session_id}")
    if cwd:
        parts.append(f"cwd: {cwd}")
    if repo_path:
        parts.append(f"repo_path: {repo_path}")
    if repo_source:
        parts.append(f"repo_source: {repo_source}")
    if repo_full_name:
        parts.append(f"repo_full_name: {repo_full_name}")
    if branch_name:
        parts.append(f"branch: {branch_name}")
    if stdout:
        parts.append(f"stdout:\n{stdout}")
    if cleaned_stderr:
        parts.append(f"stderr:\n{cleaned_stderr}")
    elif stderr and session_id:
        parts.append("stderr: session_id only; inspect the Hermes session export for deeper diagnostics")
    return "\n".join(parts)

def build_hermes_code_prompt(task: dict[str, Any], task_input_data: dict[str, Any], repo_path: str, title: str, description: str) -> str:
    task_json = pretty_json(task)
    input_json = pretty_json(task_input_data)
    repo_display = repo_path or "未提供"
    return textwrap.dedent(
        f"""
        你是 Hermes 的代码执行 worker。请直接在当前仓库里完成任务。

        仓库路径：{repo_display}
        任务 ID：{safe_text(task.get('id'), '')}
        任务标题：{title}
        任务描述：{description}

        任务输入 JSON：
        {input_json}

        任务完整 JSON：
        {task_json}

        要求：
        1. 先查看相关代码和测试。
        2. 做最小必要修改，必要时先补测试。
        3. 运行相关测试并修复失败。
        4. 最终只输出 JSON，字段建议包含 summary、changed_files、tests、notes。
        5. 如果无法完成，直接说明原因。
        """
    ).strip()

def resolve_code_task_command(task: dict[str, Any], task_input_data: dict[str, Any], repo_path: str, title: str, description: str) -> str | list[str]:
    command = os.environ.get("CODE_TASK_COMMAND") or os.environ.get("AGENT_DEV_COMMAND") or ""
    if command:
        return command
    if shutil.which("hermes"):
        prompt = build_hermes_code_prompt(task, task_input_data, repo_path, title, description)
        return ["hermes", "chat", "-Q", "-q", prompt, "-t", "terminal,file", "--yolo"]
    return ""

def git_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("GIT_HTTP_VERSION", "HTTP/1.1")
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    env.setdefault("GIT_AUTHOR_NAME", env.get("GIT_AUTHOR_NAME", "Hermes Agent"))
    env.setdefault("GIT_AUTHOR_EMAIL", env.get("GIT_AUTHOR_EMAIL", "hermes-agent@localhost"))
    env.setdefault("GIT_COMMITTER_NAME", env.get("GIT_COMMITTER_NAME", env["GIT_AUTHOR_NAME"]))
    env.setdefault("GIT_COMMITTER_EMAIL", env.get("GIT_COMMITTER_EMAIL", env["GIT_AUTHOR_EMAIL"]))
    return env

def run_git(repo_path: str, args: list[str], *, stdin_text: str = "") -> subprocess.CompletedProcess[str]:
    return run_external_command(["git", *args], cwd=repo_path, env=git_env(), stdin_text=stdin_text)

def sanitize_branch_component(value: Any, fallback: str = "task") -> str:
    text = safe_text(value, "")
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip(".-_")
    return text or fallback

def build_code_branch_name(task: dict[str, Any]) -> str:
    for candidate in (task.get("taskKey"), task.get("title"), task.get("id"), "task"):
        component = sanitize_branch_component(candidate)
        if component != "task":
            task_id = safe_text(task.get("id"), "task")
            suffix = hashlib.sha1(task_id.encode("utf-8")).hexdigest()[:8]
            return f"agent-dev/{component}-{suffix}"
    task_id = safe_text(task.get("id"), "task")
    suffix = hashlib.sha1(task_id.encode("utf-8")).hexdigest()[:8]
    return f"agent-dev/task-{suffix}"

def github_repo_full_name(project: dict[str, Any], repo_source: str | None, repo_path: str) -> str:
    owner = safe_text(project.get("owner"), "")
    repo = safe_text(project.get("repo"), "")
    if owner and repo:
        return f"{owner}/{repo}"

    for candidate in (repo_source,):
        candidate_owner_repo = github_owner_repo(candidate)
        if candidate_owner_repo:
            return "/".join(candidate_owner_repo)

    try:
        remote_url = run_git(repo_path, ["remote", "get-url", "origin"]).stdout.strip()
    except Exception:
        remote_url = ""
    candidate_owner_repo = github_owner_repo(remote_url)
    if candidate_owner_repo:
        return "/".join(candidate_owner_repo)
    return ""

def github_owner_repo(value: Any) -> tuple[str, str] | None:
    text = safe_text(value)
    if not text:
        return None
    if "github.com/" in text:
        suffix = text.split("github.com/", 1)[1].strip("/")
        suffix = suffix.removesuffix(".git")
        parts = suffix.split("/")
        if len(parts) >= 2:
            return parts[0], parts[1]
    if text.startswith("git@github.com:"):
        text = text.removeprefix("git@github.com:")
    match = re.match(r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$", text)
    if match:
        return match.group("owner"), match.group("repo")
    return None

def extract_github_pr_url(text: str) -> str | None:
    match = re.search(r"https://github\.com/[^\s]+?/pull/\d+", text)
    return match.group(0) if match else None

def repo_has_directory_contents(path: Path) -> bool:
    try:
        next(path.iterdir())
        return True
    except (StopIteration, FileNotFoundError, NotADirectoryError):
        return False

def prepare_code_repo(repo_path: str, default_branch: str, branch_name: str) -> None:
    run_git(repo_path, ["fetch", "origin", "--prune"])
    run_git(repo_path, ["checkout", default_branch])
    run_git(repo_path, ["pull", "--ff-only", "origin", default_branch])
    run_git(repo_path, ["checkout", "-B", branch_name])

def lookup_existing_pull_request(repo_path: str, repo_full_name: str, branch_name: str) -> dict[str, Any] | None:
    if not repo_full_name:
        return None
    result = run_external_command(
        ["gh", "pr", "list", "--repo", repo_full_name, "--head", branch_name, "--state", "all", "--json", "url,number,state"],
        cwd=repo_path,
        env=git_env(),
        stdin_text="",
    )
    if result.returncode != 0:
        return None
    try:
        items = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return None
    if isinstance(items, list) and items:
        first = items[0]
        if isinstance(first, dict):
            return first
    return None

def create_pull_request(
    task: dict[str, Any],
    repo_path: str,
    repo_full_name: str,
    branch_name: str,
    default_branch: str,
    title: str,
    description: str,
    commit_sha: str | None,
) -> dict[str, Any] | None:
    if not repo_full_name:
        return None

    body = textwrap.dedent(
        f"""
        ## Summary
        - Task: {safe_text(task.get('taskKey'), safe_text(task.get('id'), ''))}
        - Title: {title}
        - Branch: {branch_name}
        - Commit: {commit_sha or 'unknown'}

        ## Description
        {description or '无'}

        这是由 worker 自动创建的 PR。
        """
    ).strip()

    create_result = run_external_command(
        [
            "gh",
            "pr",
            "create",
            "--repo",
            repo_full_name,
            "--head",
            branch_name,
            "--base",
            default_branch,
            "--title",
            title,
            "--body",
            body,
        ],
        cwd=repo_path,
        env=git_env(),
        stdin_text="",
    )

    pr = lookup_existing_pull_request(repo_path, repo_full_name, branch_name)
    if pr:
        return pr

    if create_result.returncode != 0:
        return lookup_existing_pull_request(repo_path, repo_full_name, branch_name)

    url = extract_github_pr_url(create_result.stdout or create_result.stderr or "")
    if url:
        return {"url": url}
    return lookup_existing_pull_request(repo_path, repo_full_name, branch_name)

def finalize_code_repo(
    task: dict[str, Any],
    repo_path: str,
    repo_full_name: str,
    artifact_root: Path,
    branch_name: str,
    default_branch: str,
    title: str,
    description: str,
) -> dict[str, Any]:
    run_git(repo_path, ["add", "-A", "."])

    repo_root = Path(repo_path)
    try:
        artifact_rel = artifact_root.relative_to(repo_root)
    except ValueError:
        artifact_rel = None

    if artifact_rel and repo_has_directory_contents(artifact_root):
        run_git(repo_path, ["reset", "--", artifact_rel.as_posix()])

    staged = run_git(repo_path, ["diff", "--cached", "--name-only"]).stdout.strip()
    staged_files = [line for line in staged.splitlines() if line.strip()]
    if not staged_files:
        existing_pr = lookup_existing_pull_request(repo_path, repo_full_name, branch_name)
        if existing_pr and isinstance(existing_pr, dict):
            return {
                "taskType": task.get("type"),
                "title": title,
                "branch": branch_name,
                "pr_url": existing_pr.get("url"),
                "github_commit_sha": None,
                "git_pushed": False,
                "summary": "代码已执行完成，没有检测到新的仓库变更，沿用已有 PR。",
            }
        return {
            "taskType": task.get("type"),
            "title": title,
            "branch": branch_name,
            "github_commit_sha": None,
            "git_pushed": False,
            "summary": "代码已执行完成，但没有检测到可提交的仓库变更。",
        }

    commit_message = f"feat(agent-dev): {title or task.get('taskKey') or task.get('id')}"
    run_git(repo_path, ["commit", "-m", commit_message])
    commit_sha = run_git(repo_path, ["rev-parse", "HEAD"]).stdout.strip() or None
    push_stdout = run_git(repo_path, ["push", "-u", "origin", branch_name]).stdout.strip()
    pr = create_pull_request(task, repo_path, repo_full_name, branch_name, default_branch, title, description, commit_sha)

    result = {
        "taskType": task.get("type"),
        "title": title,
        "summary": "代码任务已提交到新的 Git 分支、推送到 GitHub，并创建 PR。",
        "branch": branch_name,
        "github_commit_sha": commit_sha,
        "git_pushed": True,
    }
    if pr and isinstance(pr, dict):
        if pr.get("url"):
            result["pr_url"] = pr["url"]
        if pr.get("number") is not None:
            result["pr_number"] = pr["number"]
    if push_stdout:
        result["git_push_stdout"] = push_stdout
    return result

def build_code_output(task: dict[str, Any]) -> dict[str, Any]:
    from worker import main as worker_main

    task_input_data = task_input(task)
    title = safe_text(task.get("title"), safe_text(task.get("taskKey"), "代码任务"))
    description = safe_text(task.get("description"))
    project = task.get("project") if isinstance(task.get("project"), dict) else {}
    repo_path, repo_source = worker_main.resolve_repo_path(task, task_input_data, project)
    repo_full_name = github_repo_full_name(project, repo_source, repo_path)
    command = resolve_code_task_command(task, task_input_data, repo_path, title, description)
    branch_name = build_code_branch_name(task)
    default_branch = safe_text(project.get("defaultBranch"), "main") if isinstance(project, dict) else "main"

    artifact_root = worker_main.resolve_artifact_root(task)
    report_path = artifact_root / "implementation-report.md"
    report_url = public_url_for(report_path)

    base_payload = {
        "taskType": task.get("type"),
        "title": title,
        "description": description,
        "input": task_input_data,
        "repo_path": repo_path,
        "repo_source": repo_source,
        "repo_full_name": repo_full_name,
        "branch": branch_name,
    }

    if command:
        env = os.environ.copy()
        env.update(
            {
                "TASK_ID": safe_text(task.get("id"), ""),
                "TASK_KEY": safe_text(task.get("taskKey"), ""),
                "TASK_TYPE": safe_text(task.get("type"), ""),
                "TASK_TITLE": title,
                "TASK_DESCRIPTION": description,
                "TASK_INPUT_JSON": pretty_json(task_input_data),
                "TASK_JSON": pretty_json(task),
                "TASK_OUTPUT_DIR": str(artifact_root),
                "TASK_GIT_BRANCH": branch_name,
            }
        )
        if repo_path:
            env["TASK_REPO_PATH"] = repo_path
        if repo_source:
            env["TASK_REPO_URL"] = repo_source
            if not env.get("TASK_REPO_SOURCE"):
                env["TASK_REPO_SOURCE"] = repo_source

        if repo_path:
            prepare_code_repo(repo_path, default_branch, branch_name)
        result = run_external_command(command, cwd=repo_path or None, env=env, stdin_text=pretty_json(base_payload))
        if result.returncode != 0:
            raise WorkerError(
                format_command_failure(
                    command=command,
                    cwd=repo_path or None,
                    result=result,
                    repo_path=repo_path,
                    repo_source=repo_source,
                    repo_full_name=repo_full_name,
                    branch_name=branch_name,
                )
            )
        payload = maybe_parse_stdout(result.stdout)
        payload.setdefault("taskType", task.get("type"))
        payload.setdefault("title", title)
        payload.setdefault("summary", "代码任务已由外部命令执行完成。")
        payload.setdefault("branch", branch_name)
        if repo_path:
            payload.update(finalize_code_repo(task, repo_path, repo_full_name, artifact_root, branch_name, default_branch, title, description))
        stderr = normalize_success_stderr(result.stderr)
        if stderr:
            payload.setdefault("stderr", stderr)
        payload.setdefault("stdout", result.stdout.strip())
        return payload

    report = {
        "taskType": task.get("type"),
        "title": title,
        "summary": "未配置 CODE_TASK_COMMAND / AGENT_DEV_COMMAND，已输出任务分析报告。",
        "next_steps": [
            "配置外部代码执行命令后可自动修改仓库并提交结果",
            "当前版本会生成可读的任务报告，便于人工接手",
        ],
        "input": task_input_data,
        "repo_path": repo_path,
        "repo_source": repo_source,
        "branch": branch_name,
        "report_url": report_url,
    }
    write_text(report_path, pretty_json(report) + "\n")
    return report
