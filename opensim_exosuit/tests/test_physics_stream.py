"""Exercise the native solver-to-HTTP path, including pause and torque input."""

import json
import math
from pathlib import Path
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from opensim_exosuit.physics_server import PhysicsStream, SolverHTTPServer, static_scene, viewer_html


class PhysicsStreamTests(unittest.TestCase):
    def test_actual_state_stream_and_controls(self):
        with tempfile.TemporaryDirectory() as temporary:
            stream = PhysicsStream(log_directory=temporary)
            scene = static_scene()
            self.assertFalse(set(scene) & {"times", "poses", "knee_flexion_deg", "muscles"})
            page = [viewer_html(scene)]
            server = SolverHTTPServer(("127.0.0.1", 0), stream, lambda: page[0])
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            stream.start()
            base = f"http://127.0.0.1:{server.server_port}"
            # These tests address only a loopback server; skip macOS's proxy
            # discovery, which can block unrelated local HTTP requests.
            opener = build_opener(ProxyHandler({}))

            def get():
                with opener.open(base + "/state", timeout=5) as response:
                    return json.load(response)

            def wait_for(predicate):
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    state = get()
                    self.assertNotEqual(state["status"], "error", state.get("error"))
                    if predicate(state):
                        return state
                    time.sleep(.015)
                self.fail("Timed out waiting for solver state")

            def command(action, value=None, origin=None):
                message = {"action": action}
                if value is not None:
                    message["value"] = value
                headers = {"Content-Type": "application/json"}
                if origin:
                    headers["Origin"] = origin
                request = Request(base + "/control", data=json.dumps(message).encode(), headers=headers)
                with opener.open(request, timeout=5) as response:
                    return response.status

            try:
                state = wait_for(lambda item: item.get("time_s", 0) >= .06)
                self.assertAlmostEqual(state["knee_flexion_deg"]["r"], -math.degrees(state["knee_angle_r"]), places=12)
                self.assertEqual(len(state["poses"]), len(scene["frame_names"]) * 7)
                self.assertNotIn("reference_knee_flexion_deg", state)
                self.assertIn("Manager.integrate", state["source"])
                self.assertEqual(state["status"], "running")
                with opener.open(base + "/events", timeout=5) as response:
                    self.assertEqual(response.headers.get_content_type(), "text/event-stream")
                    event = response.readline().decode()
                    self.assertTrue(event.startswith("data: "))
                    self.assertEqual(json.loads(event[6:])["source"], state["source"])
                self.assertEqual(command("pause"), 202)
                paused = wait_for(lambda item: item["status"] == "paused")
                time.sleep(.12)
                self.assertEqual(get()["time_s"], paused["time_s"])
                # A refreshed presentation can load without replacing or
                # advancing the native state being inspected.
                with opener.open(base + "/", timeout=5) as response:
                    self.assertIn(b"Live OpenSim human dynamics", response.read())
                page[0] = b"updated local viewer"
                with opener.open(base + "/", timeout=5) as response:
                    self.assertEqual(response.read(), page[0])
                self.assertEqual(get()["run_id"], paused["run_id"])
                self.assertEqual(get()["time_s"], paused["time_s"])
                self.assertEqual(command("disturb", 5), 202)
                pulsed = wait_for(lambda item: item.get("disturbance_nm") == 5)
                self.assertEqual(pulsed["time_s"], paused["time_s"])
                command("play")
                advanced = wait_for(lambda item: item["time_s"] > paused["time_s"] + .1)
                self.assertEqual(advanced["disturbance_nm"], 5)
                wait_for(lambda item: item["time_s"] >= paused["time_s"] + .44 and item["disturbance_nm"] == 0)
                command("pause")
                wait_for(lambda item: item["status"] == "paused")
                command("reset")
                reset = wait_for(lambda item: item["run_id"] != state["run_id"])
                self.assertEqual(reset["time_s"], 0)
                self.assertEqual(reset["status"], "paused")
                self.assertEqual(reset["disturbance_nm"], 0)
                for slow_rate in (.25, .1):
                    with self.subTest(speed=slow_rate):
                        before = get()
                        self.assertEqual(command("speed", slow_rate), 202)
                        configured = wait_for(lambda item: item["speed"] == slow_rate)
                        self.assertEqual(configured["status"], "paused")
                        self.assertEqual(configured["time_s"], before["time_s"])
                        self.assertEqual(command("play"), 202)
                        advanced = wait_for(
                            lambda item: item["speed"] == slow_rate
                            and item["time_s"] > configured["time_s"])
                        self.assertEqual(advanced["status"], "running")
                        # Speed changes wall-clock pacing, not the amount of
                        # native physics integrated for each emitted frame.
                        self.assertAlmostEqual(advanced["last_step_dt_s"],
                                               stream.dt_s, places=12)
                        elapsed_steps = ((advanced["time_s"] - configured["time_s"])
                                         / stream.dt_s)
                        self.assertAlmostEqual(elapsed_steps,
                                               round(elapsed_steps), places=8)
                        self.assertEqual(command("pause"), 202)
                        paused_slow = wait_for(lambda item: item["status"] == "paused")
                        self.assertEqual(paused_slow["speed"], slow_rate)
                        time.sleep(.12)
                        self.assertEqual(get()["time_s"], paused_slow["time_s"])
                with self.assertRaises(HTTPError) as bad:
                    command("speed", 100)
                self.assertEqual(bad.exception.code, 400)
                with self.assertRaises(HTTPError) as cross_site:
                    command("play", origin="https://example.org")
                self.assertEqual(cross_site.exception.code, 403)
            finally:
                stream.stop()
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)
            logs = list(Path(temporary).glob("solver_states_*.csv"))
            self.assertEqual(len(logs), 1)
            self.assertIn("knee_flexion_r_deg", logs[0].read_text())


if __name__ == "__main__":
    unittest.main()
