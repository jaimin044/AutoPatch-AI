import os
import signal
import subprocess
import time
import platform
import threading

def run_cancellable_subprocess(cmd: list[str], timeout: int, cancel_event: threading.Event, cwd: str = None) -> dict:
    """
    Runs a subprocess that can be cancelled via a threading.Event.
    For the 4-day sprint, POSIX (Linux/macOS) is fully supported using process groups.
    Windows support is left as future work.
    """
    is_posix = platform.system() != "Windows"
    
    kwargs = {}
    if is_posix:
        kwargs["start_new_session"] = True
        
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            text=True,
            **kwargs
        )
    except Exception as e:
        return {"returncode": -1, "stdout": "", "stderr": str(e)}

    start_time = time.time()
    
    while True:
        retcode = process.poll()
        if retcode is not None:
            break
            
        if cancel_event.is_set():
            _kill_process_tree(process, is_posix)
            stdout, stderr = process.communicate()
            return {"returncode": -1, "stdout": stdout, "stderr": stderr + "\nProcess cancelled."}
            
        if time.time() - start_time > timeout:
            _kill_process_tree(process, is_posix)
            stdout, stderr = process.communicate()
            return {"returncode": -1, "stdout": stdout, "stderr": stderr + f"\nProcess timed out after {timeout} seconds."}
            
        time.sleep(0.25)
        
    stdout, stderr = process.communicate()
    return {"returncode": process.returncode, "stdout": stdout, "stderr": stderr}

def _kill_process_tree(process: subprocess.Popen, is_posix: bool):
    try:
        if is_posix:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        else:
            process.kill()
    except Exception:
        pass
