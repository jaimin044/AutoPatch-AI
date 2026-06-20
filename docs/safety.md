# AutoPatch AI - Sandbox Safety & Isolation Architecture

Because AutoPatch AI executes arbitrary, potentially untrusted test suites natively pulled from GitHub repositories, security and resource isolation are top priorities. The system utilizes Docker and Linux primitives to execute these workloads within deeply constrained ephemeral sandboxes.

## 1. Per-Job Ephemeral File Isolation

Each job generates a unique, single-use directory under `~/.autopatch/sandboxes/{job_id}/`.
- **No Global Mounts**: We do not mount the parent sandbox directory into the container. Only the specific `{job_id}/repo` is mounted as `/workspace`.
- This ensures concurrent jobs cannot clobber each other's state or access another repository's sensitive data.
- **Cleanup Guarantee**: The `JobManager` wraps all Graph executions in a strict `finally` block that forcefully deletes this directory using `shutil.rmtree` when the job completes or is cancelled.

## 2. Granular Network Isolation & Revocation

The core risk of running untrusted tests is network exfiltration. We use a **two-phase networking strategy**.

1. **Phase 1 (Preparation)**: When a container starts, we attach it to a *custom*, single-use Docker Bridge Network (e.g., `autopatch-net-{job_id}`). We explicit pass DNS (`1.1.1.1`, `8.8.8.8`) to circumvent host DNS resolution issues inside isolated bridge networks. We execute `pip install` to gather dependencies.
2. **Phase 2 (Execution)**: Right before the untrusted `pytest` command is run, we invoke `network.disconnect(container, force=True)`. The custom network is destroyed. The tests run completely air-gapped from the internet.
   - *Note: We never use Docker's default `bridge` because disconnecting a running container from the default bridge is unreliable across daemon implementations.*

## 3. Strict Resource Caps

To prevent runaway processes or fork-bombs from exhausting host resources, every sandbox container enforces strict runtime constraints:
- **Memory Cap**: `256m` (configurable)
- **CPU Cap**: `1.0` (configurable)
- **PID Limit**: `128` threads/processes max.

## 4. Privilege Drops & UID Mapping

- **Dependency Installation**: `pip install` runs as `root` because the base python image installs `site-packages` globally.
- **Test Execution**: `pytest` runs mapped to the **host system's UID and GID**. 
  - *Why?* Any file created by the test suite will be cleanly owned by the host user. This avoids `PermissionError` when the host attempts to `shutil.rmtree` the directory during the cleanup phase.
- We utilize `--security-opt no-new-privileges:true` and `--cap-drop ALL` to strip any setuid execution capabilities from the container.

## 5. Defense-in-Depth Timeout Mechanisms

A malicious test might attempt to `time.sleep(99999)`. We utilize two layers of timeouts:

1. **Container-Side (Linux `timeout`)**: We prepend untrusted commands with `timeout --kill-after=5s 60s bash -lc 'pytest'`. This ensures the actual inner process tree receives `SIGTERM` and `SIGKILL`, freeing up the container daemon.
2. **Host-Side (Python `subprocess` fallback)**: The host thread uses `.communicate(timeout=...)` to prevent the agent from hanging indefinitely if the Docker CLI itself deadlocks.

## 6. Process Tree Cancellation

If a user hits "Cancel" or their browser disconnects (SSE stream drop), the host immediately sets a `threading.Event`.
Because blocking commands like `git clone` or `docker pull` cannot be cleanly interrupted via a boolean flag, we run all subprocesses using `start_new_session=True`. This places them in a dedicated Process Group.
When cancelled, we invoke `os.killpg(pid, signal.SIGKILL)`, instantly annihilating the entire process tree (e.g., `bash -> docker exec -> pytest`), guaranteeing no zombie processes are orphaned on the host machine.
