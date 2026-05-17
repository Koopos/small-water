from __future__ import annotations

import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.modules.setdefault("worker.main", sys.modules[__name__])

from worker.core.common import WorkerConfig, WorkerError, claim_task, complete_task, fail_task, fetch_task, http_json, parse_json, pretty_json, safe_text, task_artifacts, task_input, task_output
from worker.core.content import build_article_output, build_content_output, build_content_task_output, build_dating_post_output, build_hot_content_output, build_image_prompt, build_video_script_output, make_content_pages
from worker.core.code import (build_code_branch_name, build_code_output, build_hermes_code_prompt, create_pull_request, extract_github_pr_url, extract_session_id, finalize_code_repo, format_command_failure, github_owner_repo, github_repo_full_name, git_env, is_transient_git_clone_error, lookup_existing_pull_request, maybe_parse_stdout, normalize_success_stderr, prepare_code_repo, resolve_code_task_command, repo_has_directory_contents, run_git, sanitize_branch_component)
from worker.core.fs import public_url_for, resolve_artifact_root, write_json, write_placeholder_png, write_text
from worker.core.image import build_image_output
from worker.core.process import run_external_command
from worker.core.repo import clone_github_repo, github_clone_url, resolve_repo_path, worker_repo_root
from worker.core.runner import EXECUTORS, main, parse_args, run_once


__all__ = [
    'WorkerConfig', 'WorkerError', 'http_json', 'claim_task', 'fetch_task', 'complete_task', 'fail_task',
    'parse_json', 'pretty_json', 'task_input', 'task_output', 'task_artifacts', 'safe_text',
    'worker_repo_root', 'github_clone_url', 'is_transient_git_clone_error', 'clone_github_repo', 'resolve_repo_path',
    'resolve_artifact_root', 'public_url_for', 'write_text', 'write_json', 'write_placeholder_png',
    'make_content_pages', 'build_dating_post_output', 'build_article_output', 'build_hot_content_output', 'build_video_script_output', 'build_content_output', 'build_image_prompt', 'build_content_task_output',
    'run_external_command', 'maybe_parse_stdout', 'normalize_success_stderr', 'extract_session_id', 'format_command_failure', 'build_hermes_code_prompt', 'resolve_code_task_command', 'git_env', 'run_git', 'sanitize_branch_component', 'build_code_branch_name',
    'github_repo_full_name', 'github_owner_repo', 'extract_github_pr_url', 'repo_has_directory_contents', 'prepare_code_repo', 'lookup_existing_pull_request', 'create_pull_request', 'finalize_code_repo', 'build_code_output',
    'build_image_output', 'EXECUTORS', 'run_once', 'parse_args', 'main',
]

if __name__ == '__main__':
    raise SystemExit(main())
