import os
import time
import shutil
import platform
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
import docker

from .config import settings
from .subprocesses import run_cancellable_subprocess

client = docker.from_env()

@dataclass
class Sandbox:
    job_id: str
    container_id: str
    network_name: str
    repo_path: str

from typing import Optional

def host_user_or_none() -> Optional[str]:
    if platform.system() != "Windows" and hasattr(os, "getuid"):
        return f"{os.getuid()}:{os.getgid()}"
    return None

def create_sandbox(job_id: str, repo_url: str, cancel_event: threading.Event) -> Sandbox:
    """
    Creates a full sandbox environment.
    1. Per-job directory
    2. Clone repo
    3. Custom network
    4. Start container
    """
    # 1. Directory
    job_dir = settings.sandbox_root / job_id
    repo_dir = job_dir / "repo"
    job_dir.mkdir(parents=True, exist_ok=True)
    
    # 2. Clone repo
    if cancel_event.is_set():
        raise RuntimeError("Job cancelled")
        
    clone_cmd = ["git", "clone", repo_url, str(repo_dir)]
    res = run_cancellable_subprocess(clone_cmd, settings.clone_timeout, cancel_event)
    if res["returncode"] != 0:
        raise RuntimeError(f"Clone failed: {res['stderr']}")
        
    # 3. Network
    if cancel_event.is_set():
        raise RuntimeError("Job cancelled")
        
    network_name = f"autopatch-net-{job_id}"
    try:
        network = client.networks.create(network_name, driver="bridge")
    except docker.errors.APIError as e:
        raise RuntimeError(f"Network creation failed: {e}")

    # 4. Start container
    if cancel_event.is_set():
        raise RuntimeError("Job cancelled")
        
    try:
        container = client.containers.run(
            "python:3.11-slim",
            command="tail -f /dev/null",  # Keep alive
            detach=True,
            network=network_name,
            mem_limit=settings.sandbox_memory,
            nano_cpus=int(settings.sandbox_cpus * 1e9),
            pids_limit=settings.sandbox_pids,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            volumes={
                str(repo_dir): {"bind": "/workspace", "mode": "rw"}
            },
            working_dir="/workspace",
            name=f"autopatch-sandbox-{job_id}"
        )
    except Exception as e:
        # Cleanup network if container fails
        try:
            client.networks.get(network_name).remove()
        except Exception:
            pass
        raise RuntimeError(f"Container start failed: {e}")
        
    return Sandbox(
        job_id=job_id,
        container_id=container.id,
        network_name=network_name,
        repo_path=str(repo_dir)
    )

def install_dependencies(sandbox: Sandbox, cancel_event: threading.Event):
    """
    Installs dependencies inside the container as root.
    """
    install_cmd = None
    if os.path.exists(os.path.join(sandbox.repo_path, "requirements.txt")):
        install_cmd = "pip install -r requirements.txt"
    elif os.path.exists(os.path.join(sandbox.repo_path, "pyproject.toml")):
        install_cmd = "pip install ."
        
    if not install_cmd:
        return
        
    if cancel_event.is_set():
        raise RuntimeError("Job cancelled")
        
    cmd = [
        "docker", "exec", "--user", "root", sandbox.container_id,
        "bash", "-c", install_cmd
    ]
    res = run_cancellable_subprocess(cmd, settings.install_timeout, cancel_event)
    if res["returncode"] != 0:
        print(f"Warning: Install failed: {res['stderr']}")
        # We deliberately do not raise an exception here so that repos with 
        # broken pyproject.toml files can still be patched!

    # Always ensure pytest is available for validation
    pytest_cmd = [
        "docker", "exec", "--user", "root", sandbox.container_id,
        "bash", "-c", "pip install pytest"
    ]
    pytest_res = run_cancellable_subprocess(pytest_cmd, 30, cancel_event)
    if pytest_res["returncode"] != 0:
        print(f"Warning: Pytest install failed: {pytest_res['stderr']}")
    else:
        print(f"Pytest installed successfully")

def disable_network(sandbox: Sandbox):
    try:
        network = client.networks.get(sandbox.network_name)
        network.disconnect(sandbox.container_id, force=True)
    except Exception as e:
        raise RuntimeError(f"Failed to disable network: {e}")

def run_untrusted_command(sandbox: Sandbox, command: str, cancel_event: threading.Event) -> dict:
    """
    Runs untrusted code with inner timeout and host user.
    """
    user = host_user_or_none()
    user_args = ["--user", user] if user else []
    
    # Inner timeout wrapping
    inner_cmd = f"timeout --kill-after=5s {settings.command_timeout}s bash -c '{command}'"
    
    cmd = [
        "docker", "exec"
    ] + user_args + [
        sandbox.container_id,
        "bash", "-c", inner_cmd
    ]
    
    # Add a buffer for the host timeout
    host_timeout = settings.command_timeout + 10
    
    return run_cancellable_subprocess(cmd, host_timeout, cancel_event)

def cleanup_sandbox(job_id: str):
    container_name = f"autopatch-sandbox-{job_id}"
    network_name = f"autopatch-net-{job_id}"
    
    # 1. Kill inner container processes
    try:
        container = client.containers.get(container_name)
        container.kill()
    except Exception:
        pass
        
    # 2. Stop container
    try:
        container = client.containers.get(container_name)
        container.stop(timeout=1)
    except Exception:
        pass
    
    # 3. Remove container explicitly
    try:
        container = client.containers.get(container_name)
        container.remove(force=True)
    except Exception:
        pass
        
    # Wait briefly for Docker to release endpoints
    time.sleep(1)
        
    # 4. & 5. Remove network with retry
    for _ in range(3):
        try:
            network = client.networks.get(network_name)
            network.remove()
            break
        except docker.errors.NotFound:
            break
        except Exception:
            time.sleep(1)
            
    # 6. Remove files
    job_dir = settings.sandbox_root / job_id
    if job_dir.exists():
        # Trick: use Docker to bypass root-owned files from pip installs
        try:
            subprocess.run([
                "docker", "run", "--rm", "-v", f"{job_dir}:/clean", "alpine", "sh", "-c", "rm -rf /clean/*"
            ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            shutil.rmtree(job_dir, ignore_errors=True)
        except Exception:
            pass
