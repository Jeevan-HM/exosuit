"""Contract regression tests; no imports from the original hardware scripts."""

import math
import unittest

import numpy as np

from human.rl_contract import (
    FiveStrideAggregator, StrideFeatures, TimingCommand, action_to_timing,
    extract_strides, legacy_cost, observation_from_features, pressure_psi,
    reward_from_cost, sample_pressure_schedule,
)


class ActionContractTests(unittest.TestCase):
    def test_v9_absolute_seconds_endpoints(self):
        np.testing.assert_allclose(action_to_timing([-1] * 4, "v9_seconds", 2).as_tuple(),
                                   [0, .3, .7, .2])
        np.testing.assert_allclose(action_to_timing([1] * 4, "v9_seconds", 2).as_tuple(),
                                   [.3, .8, 1.4, .4])
        self.assertEqual(action_to_timing([0] * 4, "v9_seconds", 2).as_tuple(),
                         action_to_timing([0] * 4, "v9_seconds", 3).as_tuple())

    def test_percent_scales_onsets_and_durations_by_period(self):
        np.testing.assert_allclose(action_to_timing([-1] * 4, "v1_percent", 2).as_tuple(),
                                   [0, 0, 1, 0])
        np.testing.assert_allclose(action_to_timing([1] * 4, "v1_percent", 2).as_tuple(),
                                   [.4, .5, 1.48, .56])
        np.testing.assert_allclose(action_to_timing([0] * 4, "v1_percent", 2).as_tuple(),
                                   [.2, .25, 1.24, .28])

    def test_legal_actor_range_can_produce_invalid_schedule(self):
        command = action_to_timing([1, 1, -1, 1], "v9_seconds", 2)
        self.assertIn("overlapping_pressure_windows", command.validation_errors())
        with self.assertRaises(ValueError):
            pressure_psi(.8, command)
        overlong = action_to_timing([1] * 4, "v1_percent", 1)
        self.assertIn("swing_window_past_next_heelstrike", overlong.validation_errors())

    def test_shape_finite_and_range_checks(self):
        for action in ([0] * 3, [[0] * 4], [0, 0, 0, math.nan], [0, 0, 0, 1.01]):
            with self.subTest(action=action), self.assertRaises(ValueError):
                action_to_timing(action, "v1_percent", 1)
        for stride in (0, -1, math.inf, math.nan):
            with self.subTest(stride=stride), self.assertRaises(ValueError):
                action_to_timing([0] * 4, "v1_percent", stride)
        with self.assertRaises(ValueError):
            action_to_timing([0] * 4, "guess_latest_version", 1)

    def test_single_scalar_pressure_and_original_endpoint_order(self):
        command = TimingCommand(.1, .2, .7, .2, 1, "v1_percent")
        for time, expected in ((0, 0), (.1, 0), (.11, 25), (.3, 25),
                               (.31, 0), (.7, 0), (.71, 20), (.89, 20), (.91, 0)):
            self.assertEqual(pressure_psi(time, command), expected)
        times, pressure = sample_pressure_schedule(command)
        self.assertEqual(len(times), 101)
        np.testing.assert_allclose(np.diff(times), .01)
        self.assertEqual(set(pressure), {0., 20., 25.})

    def test_zero_duration_never_inflates(self):
        command = TimingCommand(.1, 0, .7, 0, 1, "v1_percent")
        _, pressure = sample_pressure_schedule(command)
        np.testing.assert_array_equal(pressure, 0)


class CostContractTests(unittest.TestCase):
    def test_percent_state_preserves_half_stance_duration(self):
        features = [.124, .375, .71, .168, .698, .1, .2, .3, 1.75]
        np.testing.assert_allclose(observation_from_features(features, "v1_percent"),
                                   [.124, .1875, .71, .168, .698])
        np.testing.assert_allclose(observation_from_features(features, "v9_seconds"),
                                   features[:5])

    def test_percent_cost_at_legacy_target(self):
        features = [.124, .375, .71, .168, .698, .1, .2, .3, 1.75]
        # Match normalized human timing to action, preserving source d1/2.
        action = [2 * .124 / .2 - 1, 2 * .1875 / .25 - 1,
                  2 * (.71 - .5) / .24 - 1, 2 * .168 / .28 - 1]
        self.assertAlmostEqual(legacy_cost(features, action, "v1_percent"), .5 * .6 ** 2)

    def test_v9_cost_at_legacy_target(self):
        features = [.232, .6, 1.2, .3, .698, .1, .2, .3, 2]
        action = [2 * .232 / .3 - 1, 2 * (.6 - .3) / .5 - 1,
                  2 * (1.2 - .7) / .7 - 1, 2 * (.3 - .2) / .2 - 1]
        self.assertAlmostEqual(legacy_cost(features, action, "v9_seconds"), .5 * 50 * .6 ** 2)

    def test_cost_is_positive_and_maximizing_reward_negative(self):
        features = [.1, .4, .7, .2, 1, .1, .2, .3, 1.5]
        cost = legacy_cost(features, [0] * 4, "v1_percent")
        self.assertGreater(cost, 0)
        self.assertEqual(reward_from_cost(cost), -cost)
        for cost in (-1, math.nan, math.inf):
            with self.assertRaises(ValueError):
                reward_from_cost(cost)

    def test_percent_cost_independent_of_stride_seconds(self):
        features = [.1, .4, .7, .2, 1, .1, .2, .3, 1.5]
        expected = legacy_cost(features, [0] * 4, "v1_percent")
        features[-1] = 2.1
        self.assertEqual(expected, legacy_cost(features, [0] * 4, "v1_percent"))


def example_trace():
    """Sample trace with actual left HS at .2, 1.2, 2.2 and peak at .95."""
    times = np.arange(251) / 100
    phase = (np.arange(251) - 20) % 100
    left = np.where(phase < 60, 700., 0.)
    right = np.where((phase >= 10) & (phase < 50), 0., 700.)
    # Strict peak at phase .75, safely after left toe-off at .60.
    angle = 1.1 - np.abs(phase / 100 - .75)
    activations = np.tile([.1, .2, .3], (len(times), 1))
    return times, angle, left, right, activations


class EventContractTests(unittest.TestCase):
    def test_contact_events_fraction_features_and_proxy_means(self):
        result = extract_strides(*example_trace())
        self.assertEqual(len(result), 2)
        self.assertTrue(all(stride.valid for stride in result))
        np.testing.assert_allclose(result[0].vector,
                                   [.1, .4, .75, .25, 1.1, .1, .2, .3, 1])
        self.assertEqual(result[0].heelstrike_start, .2)
        self.assertEqual(result[0].heelstrike_end, 1.2)
        self.assertEqual(result[0].muscle_signal_kind, "mean_simulated_activation_proxy")

    def test_seconds_and_fractions_are_explicit(self):
        times, angle, left, right, activation = example_trace()
        result = extract_strides(times * 2, angle, left, right, activation,
                                 profile="v9_seconds")
        np.testing.assert_allclose(result[0].vector[:4], [.2, .8, 1.5, .5])
        self.assertAlmostEqual(result[0].vector[8], 2)

    def test_initial_contact_is_not_manufactured_heelstrike(self):
        times, angle, left, right, activation = example_trace()
        left[:] = 700
        self.assertEqual(extract_strides(times, angle, left, right, activation), [])

    def test_no_peak_or_single_support_is_flagged(self):
        times, angle, left, right, activation = example_trace()
        results = extract_strides(times, times, left, right, activation)
        self.assertFalse(results[0].valid)
        self.assertIn("missing_strict_swing_knee_peak", results[0].errors)
        results = extract_strides(times, angle, left, np.ones_like(right) * 700, activation)
        self.assertIn("missing_left_single_support", results[0].errors)
        self.assertIsNone(results[0].vector)

    def test_absent_activation_is_not_zero_emg(self):
        result = extract_strides(*example_trace()[:4])
        self.assertFalse(result[0].valid)
        self.assertIn("missing_activation_proxy", result[0].errors)
        self.assertIsNone(result[0].vector)

    def test_threshold_is_strictly_greater_than_100_n(self):
        times, angle, left, right, activation = example_trace()
        left[left == 700] = 100
        self.assertEqual(extract_strides(times, angle, left, right, activation), [])

    def test_misaligned_nonfinite_or_nonstrict_time_is_rejected(self):
        trace = example_trace()
        with self.assertRaises(ValueError):
            extract_strides(trace[0][:-1], *trace[1:])
        with self.assertRaises(ValueError):
            extract_strides(np.zeros_like(trace[0]), *trace[1:])
        activation = trace[-1].copy()
        activation[0, 0] = -1
        with self.assertRaises(ValueError):
            extract_strides(*trace[:4], activation)


class AggregationTests(unittest.TestCase):
    def test_five_valid_strides_mean_no_four_over_five_bug(self):
        aggregator = FiveStrideAggregator()
        features = extract_strides(*example_trace())[0]
        for _ in range(4):
            self.assertIsNone(aggregator.add(features))
        np.testing.assert_allclose(aggregator.add(features), features.vector)
        self.assertEqual(aggregator.pending_count, 0)

    def test_invalid_stride_not_counted_and_profile_cannot_mix(self):
        aggregator = FiveStrideAggregator()
        invalid = StrideFeatures(0, 1, "v1_percent", None, ("missing_peak",))
        self.assertIsNone(aggregator.add(invalid))
        self.assertEqual(aggregator.pending_count, 0)
        other = extract_strides(*example_trace(), profile="v9_seconds")[0]
        with self.assertRaises(ValueError):
            aggregator.add(other)

    def test_settling_skip_is_explicit_and_reset_per_block(self):
        aggregator = FiveStrideAggregator(warmup_strides=1)
        features = extract_strides(*example_trace())[0]
        self.assertIsNone(aggregator.add(features))
        self.assertEqual(aggregator.pending_count, 0)
        for _ in range(4):
            self.assertIsNone(aggregator.add(features))
        self.assertIsNotNone(aggregator.add(features))
        self.assertIsNone(aggregator.add(features))
        self.assertEqual(aggregator.pending_count, 0)


if __name__ == "__main__":
    unittest.main()
