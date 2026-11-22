"""Run forward-dynamics diagnostics; stop explicitly on a fall."""
import json
from .backend import HumanBackend, ROOT


def main():
    results = []
    for parameter in ("tutorial_prep.txt", "tutorial.txt"):
        for torque in (0.0, 8.0, -8.0):
            human = HumanBackend(ROOT / "parameters" / parameter)
            contacts = []
            for _ in range(3000):
                state = human.step(0.01, torque)
                contacts.append((state["left_grf_n"] > 100, state["right_grf_n"] > 100))
                if state["fallen"]:
                    break
            results.append({
                "parameter_file": parameter,
                "constant_knee_torque_nm": torque,
                "requested_duration_s": 30.0,
                "completed_time_s": state["time_s"],
                "distance_m": state["distance_m"],
                "fallen": state["fallen"],
                "ground_contact_state_changes": sum(a != b for a, b in zip(contacts, contacts[1:])),
            })
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
