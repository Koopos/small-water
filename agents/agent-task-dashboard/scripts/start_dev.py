from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ProcessSpec:
    name: str
    command: list[str]
    cwd: Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_state_path(root: Path | None = None) -> Path:
    base = root or repo_root()
    return base / ".run" / "dev-launcher.json"


def normalize_worker_pools(worker_pool: str) -> list[str]:
    pool = worker_pool.strip().lower()
    if pool in {"all", "*", "default"}:
        return ["code", "image", "content"]
    values = [item.strip() for item in worker_pool.split(",") if item.strip()]
    allowed = [item for item in values if item in {"code", "image", "content"}]
    return allowed or ["content"]


def build_process_specs(
    *,
    repo_root: Path,
    api_base_url: str,
    worker_pool: str,
    include_worker: bool = True,
) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = [
        {
            "name": "next",
            "command": ["npm", "run", "dev"],
            "cwd": repo_root,
        }
    ]
    if include_worker:
        for pool in normalize_worker_pools(worker_pool):
            specs.append(
                {
                    "name": f"worker-{pool}",
                    "command": [
                        sys.executable,
                        "worker/main.py",
                        "--api-base-url",
                        api_base_url,
                        "--worker-pool",
                        pool,
                    ],
                    "cwd": repo_root,
                }
            )
    return specs


def ensure_run_dir(root: Path) -> Path:
    run_dir = root / ".run"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_state(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_state(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def terminate_pid(pid: int, *, timeout: float = 8.0) -> bool:
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except PermissionError:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False

    deadline = time.time() + timeout
    while time.time() < deadline:
        if not pid_is_running(pid):
            return True
        time.sleep(0.2)

    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    except PermissionError:
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception:
            return False
    return True


def stop_from_state(state_path: Path) -> int:
    state = read_state(state_path)
    if not state:
        print(f"没有找到运行状态：{state_path}")
        return 0

    pids = state.get("pids", {})
    stopped = 0
    for name, pid_value in pids.items():
        try:
            pid = int(pid_value)
        except (TypeError, ValueError):
            continue
        if terminate_pid(pid):
            print(f"已停止 {name}: PID {pid}")
            stopped += 1
        else:
            print(f"停止失败 {name}: PID {pid}")

    try:
        state_path.unlink()
    except FileNotFoundError:
        pass
    return 0 if stopped else 1


def wait_for_port(host: str, port: int, timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            if sock.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.25)
    return False


def launch_process(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.Popen[str]:
    return subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        start_new_session=True,
        text=True,
    )


def collect_process_state(processes: dict[str, subprocess.Popen[str]]) -> dict[str, int]:
    return {name: proc.pid for name, proc in processes.items()}


def write_launch_state(
    *,
    state_path: Path,
    repo_root: Path,
    api_base_url: str,
    worker_pool: str,
    include_worker: bool,
    processes: dict[str, subprocess.Popen[str]],
) -> None:
    write_state(
        state_path,
        {
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "repo_root": str(repo_root),
            "api_base_url": api_base_url,
            "worker_pool": worker_pool,
            "include_worker": include_worker,
            "pids": collect_process_state(processes),
        },
    )


def launch_processes(process_specs: list[dict[str, object]], env: dict[str, str]) -> dict[str, subprocess.Popen[str]]:
    processes: dict[str, subprocess.Popen[str]] = {}
    for spec in process_specs:
        name = str(spec["name"])
        proc = launch_process(list(spec["command"]), Path(spec["cwd"]), env.copy())
        processes[name] = proc
        print(f"已启动 {name}: PID {proc.pid}")
    return processes


def supervise_forever(
    *,
    processes: dict[str, subprocess.Popen[str]],
    process_specs: dict[str, dict[str, object]],
    env: dict[str, str],
    state_path: Path,
    repo_root: Path,
    api_base_url: str,
    worker_pool: str,
    include_worker: bool,
    next_port: int,
) -> int:
    worker_names = [name for name in process_specs if name != "next"]
    while True:
        next_proc = processes.get("next")
        if next_proc is None:
            raise RuntimeError("missing next process")

        if next_proc.poll() is not None:
            print("next 已退出，正在重启整套服务...")
            for name in worker_names:
                proc = processes.get(name)
                if proc is not None and proc.poll() is None:
                    terminate_pid(proc.pid)
            next_proc = launch_process(list(process_specs["next"]["command"]), Path(process_specs["next"]["cwd"]), env.copy())
            processes["next"] = next_proc
            print(f"已重启 next: PID {next_proc.pid}")
            if not wait_for_port("127.0.0.1", next_port, timeout=90.0):
                print(f"Next.js 重启后仍未在 {next_port} 端口就绪，稍后重试")
                time.sleep(3)
                continue
            for name in worker_names:
                worker_spec = process_specs[name]
                proc = launch_process(list(worker_spec["command"]), Path(worker_spec["cwd"]), env.copy())
                processes[name] = proc
                print(f"已重启 {name}: PID {proc.pid}")
            write_launch_state(
                state_path=state_path,
                repo_root=repo_root,
                api_base_url=api_base_url,
                worker_pool=worker_pool,
                include_worker=include_worker,
                processes=processes,
            )
        else:
            for name in worker_names:
                proc = processes.get(name)
                if proc is not None and proc.poll() is not None:
                    worker_spec = process_specs[name]
                    print(f"{name} 已退出，正在重启...")
                    replacement = launch_process(list(worker_spec["command"]), Path(worker_spec["cwd"]), env.copy())
                    processes[name] = replacement
                    print(f"已重启 {name}: PID {replacement.pid}")
                    write_launch_state(
                        state_path=state_path,
                        repo_root=repo_root,
                        api_base_url=api_base_url,
                        worker_pool=worker_pool,
                        include_worker=include_worker,
                        processes=processes,
                    )
        time.sleep(1)


def start_project(
    *,
    repo_root: Path,
    api_base_url: str,
    worker_pool: str,
    include_worker: bool,
    restart: bool,
    next_port: int,
) -> int:
    state_path = default_state_path(repo_root)
    if restart:
        state = read_state(state_path)
        if state and isinstance(state.get("pids"), dict):
            for pid_value in state["pids"].values():
                try:
                    terminate_pid(int(pid_value))
                except (TypeError, ValueError):
                    continue

    process_specs = build_process_specs(
        repo_root=repo_root,
        api_base_url=api_base_url,
        worker_pool=worker_pool,
        include_worker=include_worker,
    )
    process_specs_by_name = {str(spec["name"]): spec for spec in process_specs}
    env = os.environ.copy()
    env["PORT"] = str(next_port)

    try:
        processes = launch_processes(process_specs, env)
        next_proc = processes["next"]
        if not wait_for_port("127.0.0.1", next_port, timeout=90.0):
            raise RuntimeError(f"Next.js 没有在 {next_port} 端口上及时启动")

        write_launch_state(
            state_path=state_path,
            repo_root=repo_root,
            api_base_url=api_base_url,
            worker_pool=worker_pool,
            include_worker=include_worker,
            processes=processes,
        )

        print("")
        print(f"Next.js: http://127.0.0.1:{next_port}")
        if include_worker:
            print(f"Worker pools: {', '.join(normalize_worker_pools(worker_pool))}")
        print(f"状态文件: {state_path}")
        print("按 Ctrl+C 可停止当前前台会话；或者运行 --stop 清理上次启动的进程。")

        return supervise_forever(
            processes=processes,
            process_specs=process_specs_by_name,
            env=env,
            state_path=state_path,
            repo_root=repo_root,
            api_base_url=api_base_url,
            worker_pool=worker_pool,
            include_worker=include_worker,
            next_port=next_port,
        )
    except KeyboardInterrupt:
        print("\n收到中断，正在停止进程...")
        return 130
    except Exception as exc:
        print(f"启动失败：{exc}", file=sys.stderr)
        return 1
    finally:
        state = read_state(state_path)
        if state and isinstance(state.get("pids"), dict):
            for pid_value in state["pids"].values():
                try:
                    terminate_pid(int(pid_value))
                except (TypeError, ValueError):
                    continue


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="一键启动 Next.js + Python worker")
    parser.add_argument("--root", default=str(repo_root()), help="项目根目录")
    parser.add_argument("--api-base-url", default=os.environ.get("API_BASE_URL", "http://127.0.0.1:3000"))
    parser.add_argument("--worker-pool", default=os.environ.get("WORKER_POOL", "all"))
    parser.add_argument("--no-worker", action="store_true", help="只启动 Next.js")
    parser.add_argument("--no-restart", action="store_true", help="启动时不清理上次保存的进程")
    parser.add_argument("--stop", action="store_true", help="停止上次启动保存的进程")
    parser.add_argument("--port", type=int, default=3000, help="Next.js 端口")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    root = Path(args.root).resolve()
    state_path = default_state_path(root)

    if args.stop:
        return stop_from_state(state_path)

    return start_project(
        repo_root=root,
        api_base_url=args.api_base_url,
        worker_pool=args.worker_pool,
        include_worker=not args.no_worker,
        restart=not args.no_restart,
        next_port=args.port,
    )


if __name__ == "__main__":
    raise SystemExit(main())
