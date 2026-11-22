"""Stop the verified local OpenSim solver, including a Codex-started instance."""

import argparse
import http.client
import json
import os
import re
import signal
import subprocess
import time


def _listener_pids(port):
    result = subprocess.run(
        ["/usr/sbin/lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
        capture_output=True, text=True, check=False)
    if result.returncode not in (0, 1):
        raise RuntimeError("Could not check the local solver listener")
    return {int(value) for value in result.stdout.split() if value.isdecimal()}


def solver_listener(port):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        connection.request("GET", "/state")
        response = connection.getresponse()
        state = json.loads(response.read())
        if response.status != 200 or not isinstance(state, dict) or state.get("application") != "opensim-physics-live":
            raise RuntimeError(f"Port {port} belongs to a different service; nothing was stopped")
    except ConnectionRefusedError:
        return None
    finally:
        connection.close()
    pids = _listener_pids(port)
    if len(pids) != 1:
        raise RuntimeError("Could not identify one OpenSim listener; nothing was stopped")
    pid = pids.pop()
    process = subprocess.run(["/bin/ps", "-ww", "-p", str(pid), "-o", "uid=,command="],
                             capture_output=True, text=True, check=True)
    uid, command = process.stdout.strip().split(maxsplit=1)
    if (int(uid) != os.getuid() or not re.search(
            r"(?:^|\s)-m\s+opensim_exosuit\.physics_server(?:\s|$)", command)):
        raise RuntimeError("The listener is not your OpenSim solver; nothing was stopped")
    return pid, state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--status", action="store_true", help="Report the solver without stopping it")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    try:
        listener = solver_listener(args.port)
        if listener is None:
            print("The OpenSim solver is already stopped.")
            return
        pid, state = listener
        if args.status:
            print(f"OpenSim solver process {pid}: {state['status']}, "
                  f"simulation time {state.get('time_s', 0):.2f} s. Nothing was stopped.")
            return
        # SIGTERM is handled by physics_server.main(), which closes the native
        # integration worker and flushes its CSV before exiting.
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            # A terminated child can remain a zombie until its parent reaps
            # it. The solver is stopped once its listening socket is closed.
            if pid not in _listener_pids(args.port):
                print("OpenSim stopped. You can close the viewer or restart with Run_OpenSim_Physics.command.")
                return
            time.sleep(.1)
        raise RuntimeError("A stop was requested, but OpenSim has not exited yet")
    except (OSError, ValueError, RuntimeError, http.client.HTTPException,
            subprocess.SubprocessError) as exc:
        raise SystemExit(f"Could not stop OpenSim: {exc}") from exc


if __name__ == "__main__":
    main()
