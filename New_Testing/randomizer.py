import itertools
import random


def generate_combinations():
    # Define condition variables
    speeds = [0.8, 1.1]
    inclines = [0, 6]

    # The 4 unique combinations: (0.8, 0), (0.8, 6), (1.1, 0), (1.1, 6)
    base_conditions = list(itertools.product(speeds, inclines))
    
    trials = []

    # 1. NOEXO: 1 per combination (4 trials total)
    noexo_conds = base_conditions.copy()
    random.shuffle(noexo_conds)
    for sp, inc in noexo_conds:
        trials.append({"mode": "NOEXO", "speed": sp, "incline": inc})

    # 2. EXOINACTIVE: 1 per combination (4 trials total)
    exoinactive_conds = base_conditions.copy()
    random.shuffle(exoinactive_conds)
    for sp, inc in exoinactive_conds:
        trials.append({"mode": "EXOINACTIVE", "speed": sp, "incline": inc})

    # 3. EXOACTIVE: 2 per combination (8 trials total) - satisfies "2 trials per combination"
    exoactive_conds = base_conditions * 2
    random.shuffle(exoactive_conds)
    for sp, inc in exoactive_conds:
        trials.append({"mode": "EXOACTIVE", "speed": sp, "incline": inc})

    # 4. EXOACTIVEBASELINE: Fixed conditions, 2 trials
    for _ in range(2):
        trials.append({"mode": "EXOACTIVEBASELINE", "speed": 1.1, "incline": 0})

    # Order is maintained as added: NOEXO, EXOINACTIVE, EXOACTIVE, EXOBASELINE

    return trials


if __name__ == "__main__":
    trials = generate_combinations()
    print("=== Generated Experimental Trials ===")
    for i, t in enumerate(trials, start=1):
        print(
            f"Trial {i}: Mode = {t['mode']:<18} | Speed = {t['speed']:>3} m/s | Incline = {t['incline']} degrees"
        )
