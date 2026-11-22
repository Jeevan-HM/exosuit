"""Stream native OpenSim forward-dynamics states to a local knee-angle viewer.

Only the solver thread touches the OpenSim model. HTTP controls enter a queue;
SSE subscribers receive copies of states that this thread has integrated. The
browser receives static anatomy, never the reference gait's recorded poses or
knee trajectory. No experimental hardware or network service is controlled.
"""

import argparse
import csv
from datetime import datetime
import json
import math
from pathlib import Path
import queue
import secrets
import signal
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
from urllib.parse import urlparse
import webbrowser

from .settings import PACKAGE_DIR
from .walking import DEFAULT_OUTPUT


def static_scene(directory=DEFAULT_OUTPUT):
    """Keep just immutable anatomy from the native mesh export."""
    directory = Path(directory).resolve()
    data_path = directory / "live_data.json"
    if not data_path.is_file():
        from .live_viewer import build_live_viewer
        build_live_viewer(directory)
    data = json.loads(data_path.read_text())
    scene = {key: data[key] for key in ("meshes", "frame_names", "bounds")}
    scene.update(schema_version=1, source={
        "engine": "OpenSim forward dynamics",
        "setup": "Supported human, torque control, no exosuit",
        "angle_source": "Coordinate.getValue on the integrated SimTK State",
    })
    # Keep reference times/poses/angles out of the browser by construction.
    return scene


def viewer_html(scene):
    template = (PACKAGE_DIR / "physics_viewer.template.html").read_text()
    if template.count("__LIVE_DATA_JSON__") != 1:
        raise ValueError("Expected exactly one static anatomy placeholder")
    payload = json.dumps(scene, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")
    return template.replace("__LIVE_DATA_JSON__", payload).encode()


class PhysicsStream:
    """Own one evolving solver state and publish its latest integrated sample."""

    def __init__(self, directory=DEFAULT_OUTPUT, dt_s=.02, log_directory=None):
        self.directory = Path(directory).resolve()
        self.dt_s = dt_s
        if not math.isfinite(dt_s) or not .005 <= dt_s <= .05:
            raise ValueError("Solver control interval must be 0.005–0.05 seconds")
        self.log_directory = Path(log_directory or self.directory / "physics_output")
        self.condition = threading.Condition()
        self.commands = queue.Queue(maxsize=100)
        self.stopping = threading.Event()
        self.thread = None
        self.sequence = 0
        self.run_id = secrets.token_hex(6)
        self.latest = {"status": "starting", "sequence": 0, "run_id": self.run_id,
                       "application": "opensim-physics-live", "api_version": 1}
        self.speed = 1.
        self.paused = False
        self.error = None

    def start(self):
        if self.thread is not None:
            raise RuntimeError("The solver stream has already been started")
        self.thread = threading.Thread(target=self._solve, name="OpenSim solver", daemon=True)
        self.thread.start()

    def stop(self):
        self.stopping.set()
        with self.condition:
            self.condition.notify_all()
        if self.thread is not None:
            self.thread.join(timeout=10)

    def control(self, action, value=None):
        if self.error or self.stopping.is_set():
            raise RuntimeError(self.error or "The solver has stopped")
        if action not in ("play", "pause", "reset", "speed", "disturb"):
            raise ValueError("Unknown simulation control")
        if action == "speed":
            if isinstance(value, bool) or value not in (.1, .25, .5, 1, 1.5, 2):
                raise ValueError("Speed must be 0.1, 0.25, 0.5, 1, 1.5, or 2")
        if action == "disturb":
            if value is None:
                value = 5.
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > 10:
                raise ValueError("Knee torque pulse must be finite and within ±10 Nm")
        try:
            self.commands.put_nowait((action, value))
        except queue.Full as exc:
            raise ValueError("Too many pending simulation controls") from exc

    def snapshot(self):
        with self.condition:
            return dict(self.latest)

    def wait_sample(self, sequence, timeout=10):
        with self.condition:
            self.condition.wait_for(
                lambda: self.latest["sequence"] != sequence or self.stopping.is_set(), timeout)
            return dict(self.latest)

    def _publish(self, frame=None, **extras):
        # Never transmit reference angles: they are controller inputs, not output.
        frame = dict(frame or {})
        for key in tuple(frame):
            if key.startswith("reference_"):
                del frame[key]
        self.sequence += 1
        frame.update(sequence=self.sequence, run_id=self.run_id,
                     status="paused" if self.paused else "running", speed=self.speed,
                     application="opensim-physics-live", api_version=1,
                     source="OpenSim Manager.integrate → Coordinate.getValue")
        frame.update(extras)
        # Refuse NaNs rather than silently turning invalid physics into a trace.
        json.dumps(frame, allow_nan=False)
        with self.condition:
            self.latest = frame
            self.condition.notify_all()

    def _solve(self):
        log_handle = None
        try:
            from .physics_model import PhysicsSimulation
            self.log_directory.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            self.log_path = self.log_directory / f"solver_states_{stamp}.csv"
            log_handle = self.log_path.open("w", newline="", buffering=1)
            writer = csv.writer(log_handle)
            writer.writerow(("run_id", "sequence", "time_s", "knee_flexion_r_deg",
                             "knee_flexion_l_deg", "pelvis_height_m", "right_knee_pulse_nm"))
            simulation = PhysicsSimulation(directory=self.directory)
            frame = simulation.snapshot()
            pulse_until = None
            pulse_nm = 0.
            self._publish(frame, disturbance_nm=0.)
            deadline = time.monotonic()
            while not self.stopping.is_set():
                changed = False
                while True:
                    try:
                        action, value = self.commands.get_nowait()
                    except queue.Empty:
                        break
                    changed = True
                    if action == "play":
                        self.paused = False
                    elif action == "pause":
                        self.paused = True
                    elif action == "speed":
                        self.speed = float(value)
                    elif action == "reset":
                        simulation.set_parameter("knee_disturbance_nm", 0.)
                        simulation.reset()
                        frame = simulation.snapshot()
                        self.run_id = secrets.token_hex(6)
                        pulse_until, pulse_nm = None, 0.
                    elif action == "disturb":
                        pulse_nm = float(value)
                        pulse_until = frame["time_s"] + .4
                        simulation.set_parameter("knee_disturbance_nm", pulse_nm)
                    deadline = time.monotonic()
                if changed:
                    self._publish(frame, disturbance_nm=pulse_nm)
                if self.paused:
                    self.stopping.wait(.025)
                    continue
                if pulse_until is not None and frame["time_s"] >= pulse_until - 1e-9:
                    simulation.set_parameter("knee_disturbance_nm", 0.)
                    pulse_until, pulse_nm = None, 0.
                step_start = time.monotonic()
                frame = simulation.step(self.dt_s)
                compute_s = time.monotonic() - step_start
                self._publish(frame, disturbance_nm=pulse_nm, step_compute_ms=round(1000 * compute_s, 2))
                angles = frame["knee_flexion_deg"]
                writer.writerow((self.run_id, self.sequence, frame["time_s"], angles["r"],
                                 angles["l"], frame["pelvis_height_m"], pulse_nm))
                deadline += self.dt_s / self.speed
                # Pace only the solver. Browser clocks never generate a state.
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    self.stopping.wait(remaining)
                elif remaining < -.25:
                    deadline = time.monotonic()
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            self._publish(self.snapshot(), status="error", error=self.error)
            print(f"OpenSim solver stopped: {self.error}", flush=True)
        finally:
            if log_handle is not None:
                log_handle.close()


class SolverHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, stream, html):
        self.stream, self.html = stream, html
        super().__init__(address, SolverRequestHandler)

    def server_bind(self):
        # The address is loopback-only. A reverse-DNS lookup in HTTPServer's
        # default implementation can delay startup on an offline Mac.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]


class SolverRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            # Closing/reloading a local browser tab is normal, including while
            # the next HTTP keep-alive request or streamed frame is pending.
            pass

    def log_message(self, *args):
        pass

    def _response(self, code, body, content_type="application/json"):
        if not isinstance(body, bytes):
            body = json.dumps(body, allow_nan=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _same_origin(self):
        # Local viewer only. Reject cross-site control/fetch attempts.
        origin = self.headers.get("Origin")
        return origin is None or origin == f"http://{self.headers.get('Host')}"

    def do_GET(self):
        path = urlparse(self.path).path
        if not self._same_origin():
            self._response(403, {"error": "Use the local solver page"})
        elif path == "/":
            html = self.server.html() if callable(self.server.html) else self.server.html
            self._response(200, html, "text/html; charset=utf-8")
        elif path == "/state":
            self._response(200, self.server.stream.snapshot())
        elif path == "/events":
            self._events()
        elif path == "/favicon.ico":
            self._response(204, b"", "image/x-icon")
        else:
            self._response(404, {"error": "Unknown solver route"})

    def _events(self):
        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        sequence = -1
        stream = self.server.stream
        try:
            while not stream.stopping.is_set():
                frame = stream.wait_sample(sequence)
                if frame["sequence"] != sequence:
                    payload = json.dumps(frame, separators=(",", ":"), allow_nan=False)
                    self.wfile.write(f"data: {payload}\n\n".encode())
                    sequence = frame["sequence"]
                else:
                    self.wfile.write(b": solver connection\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass

    def do_POST(self):
        if urlparse(self.path).path != "/control":
            self._response(404, {"error": "Unknown solver route"})
            return
        if not self._same_origin() or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            self._response(403, {"error": "Use the local solver controls"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 1024:
                raise ValueError("Invalid control message size")
            command = json.loads(self.rfile.read(length))
            if not isinstance(command, dict):
                raise ValueError("Expected a control object")
            self.server.stream.control(command.get("action"), command.get("value"))
            self._response(202, {"queued": True})
        except RuntimeError as exc:
            self._response(503, {"error": str(exc)})
        except (ValueError, TypeError) as exc:
            self._response(400, {"error": str(exc)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--dt", type=float, default=.02)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    stream = PhysicsStream(args.directory, args.dt)
    scene = static_scene(args.directory)
    # A page refresh can load presentation fixes while the current native
    # solver state keeps running. Only immutable anatomy is embedded here.
    html = lambda: viewer_html(scene)
    try:
        server = SolverHTTPServer(("127.0.0.1", args.port), stream, html)
    except OSError as exc:
        # Reopening the launcher reconnects to its existing solver rather than
        # starting a competing simulation or killing another local service.
        connection = http.client.HTTPConnection("127.0.0.1", args.port, timeout=2)
        try:
            connection.request("GET", "/state")
            response = connection.getresponse()
            existing = json.loads(response.read())
            if response.status == 200 and isinstance(existing, dict) and existing.get("application") == "opensim-physics-live":
                url = f"http://127.0.0.1:{args.port}/"
                print(f"The OpenSim solver is already running: {url}", flush=True)
                print("This window reconnects to the existing solver. To stop it, "
                      "use Stop_OpenSim_Physics.command.", flush=True)
                if not args.no_browser:
                    webbrowser.open(url)
                return
        except (OSError, ValueError, http.client.HTTPException):
            pass
        finally:
            connection.close()
        raise SystemExit(f"Cannot start the local solver viewer on port {args.port}: {exc}") from exc
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"OpenSim physics + live knee plot: {url}", flush=True)
    print("Supported human · torque-controlled forward dynamics · no exosuit", flush=True)
    print("Keep this window open. Press Control-C to stop the solver.", flush=True)
    stream.start()
    if not args.no_browser:
        webbrowser.open(url)

    def stop_signal(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop_signal)
    try:
        server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:
        print("\nStopping OpenSim…", flush=True)
    finally:
        stream.stop()
        server.server_close()
        if getattr(stream, "log_path", None):
            print(f"Actual solver samples saved: {stream.log_path}", flush=True)


if __name__ == "__main__":
    main()
