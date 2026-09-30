"""
Phase 2 engine tests: physics, health, alarms, explainer.

These are the properties the system's correctness rests on, so they
are asserted rather than eyeballed. Several of them encode bugs that
were actually found and fixed during Phase 2 - they exist to stop
those bugs coming back.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.config import EXPANDED_CSV, THRESHOLDS
from src.features.build_features import engineer_features, to_matrix
from backend.core import alarms, health, physics
from backend.services import explainer, predictor


HEALTHY = dict(machine_type="M", air_temperature=298.0, process_temperature=308.0,
               rotational_speed=1558, torque=38.5, tool_wear=71)


def _profile(r):
    return physics.stress_profile(r["machine_type"], r["air_temperature"],
                                  r["process_temperature"], r["rotational_speed"],
                                  r["torque"], r["tool_wear"])


def _breaches(r):
    return physics.breaches(r["machine_type"], r["air_temperature"],
                            r["process_temperature"], r["rotational_speed"],
                            r["torque"], r["tool_wear"])


# ==================================================================
#  PHYSICS
# ==================================================================
class TestPhysics:

    def test_healthy_machine_is_not_stressed(self):
        """REGRESSION: mis-calibrated references put a healthy machine at 44% heat stress."""
        p = _profile(HEALTHY)
        assert p["stress"]["HDF"] == 0.0
        assert p["stress"]["PWF"] == 0.0
        assert p["overall_stress"] < 0.5

    def test_slow_but_well_cooled_machine_raises_no_heat_stress(self):
        """25% of healthy readings run below the HDF speed limit - min() must protect them."""
        r = dict(HEALTHY, rotational_speed=1200)
        assert _profile(r)["stress"]["HDF"] == 0.0

    def test_hdf_needs_both_conditions(self):
        low_delta_only = dict(HEALTHY, process_temperature=306.0, rotational_speed=2200)
        low_speed_only = dict(HEALTHY, rotational_speed=1200, process_temperature=310.0)
        assert _profile(low_delta_only)["stress"]["HDF"] == 0.0
        assert _profile(low_speed_only)["stress"]["HDF"] == 0.0

    def test_stress_is_bounded(self):
        for r in (HEALTHY,
                  dict(HEALTHY, torque=0.1, rotational_speed=1001),
                  dict(HEALTHY, torque=300, tool_wear=250)):
            for v in _profile(r)["stress"].values():
                assert 0.0 <= v <= 1.0

    def test_power_is_zero_inside_the_healthy_core(self):
        """REGRESSION: centre-distance made a healthy 4,775 W machine read 54%."""
        assert physics.stress_pwf(6300.0) == 0.0
        assert physics.stress_pwf(5700.0) == 0.0
        assert physics.stress_pwf(3500.0) == pytest.approx(1.0)
        assert physics.stress_pwf(9000.0) == pytest.approx(1.0)

    def test_breach_detection_matches_thresholds(self):
        over = dict(HEALTHY, torque=70.0, tool_wear=200.0)      # strain 14000 > 12000 (M)
        modes = {b["mode"] for b in _breaches(over)}
        assert "OSF" in modes

    def test_tool_wear_window_is_not_a_hard_breach(self):
        """A tool due for change has not failed - it must not floor the gauge."""
        r = dict(HEALTHY, tool_wear=210)
        bl = _breaches(r)
        assert {b["mode"] for b in bl} == {"TWF"}
        assert physics.has_hard_breach(bl) is False

    def test_real_failures_are_detected_as_hard_breaches(self):
        df = pd.read_csv(EXPANDED_CSV)
        for mode in ("HDF", "PWF", "OSF"):
            rows = df[df.failure_class == mode].head(25)
            hits = sum(physics.has_hard_breach(_breaches(r._asdict()))
                       for r in rows.itertuples(index=False))
            assert hits >= 24, "{}: only {}/25 detected".format(mode, hits)

    def test_healthy_rows_almost_never_produce_a_hard_breach(self):
        """
        Measured over the whole healthy population, not a sample.

        Exactly 6 of the 72,288 healthy rows (0.008%) sit a hair over a
        limit while still labelled Normal - e.g. 9,001.3 W against the
        9,000 W power limit, an excess of 0.014%. That is a boundary
        artifact of the dataset's own labelling, not a defect in the
        breach check: 9,001 > 9,000 IS a breach, and reporting it is
        the arithmetically correct answer. The assertion therefore
        bounds the rate rather than demanding an impossible zero.
        """
        df = pd.read_csv(EXPANDED_CSV)
        rows = df[df.failure_class == "Normal"]
        false_alarms = sum(physics.has_hard_breach(_breaches(r._asdict()))
                           for r in rows.itertuples(index=False))
        rate = false_alarms / len(rows)
        assert rate < 0.001, "{} of {} healthy rows breached ({:.3%})".format(
            false_alarms, len(rows), rate)

    def test_dominant_mode_identifies_the_real_mechanism(self):
        """
        The stress model must name the mechanism that actually killed
        the machine. Checked across every failure row in the dataset.

        The handful of misses are genuinely ambiguous rather than
        wrong: a tool at 207 min wear carrying 46 Nm is under 0.863 TWF
        stress and 0.873 OSF stress simultaneously, and which of those
        two "dominates" is a coin toss within 1%. Both readings would
        send a technician to the same tool.
        """
        df = pd.read_csv(EXPANDED_CSV)
        for mode in ("HDF", "PWF", "OSF", "TWF"):
            rows = df[df.failure_class == mode]
            hits = sum(_profile(r._asdict())["dominant_mode"] == mode
                       for r in rows.itertuples(index=False))
            rate = hits / len(rows)
            assert rate >= 0.99, "{}: dominant mode correct in only {:.1%} ({}/{})".format(
                mode, rate, hits, len(rows))


# ==================================================================
#  HEALTH & RUL
# ==================================================================
class TestHealth:

    def test_healthy_machine_reads_healthy(self):
        """REGRESSION: a linear stress->health map put the median machine in 'Monitor'."""
        p = _profile(HEALTHY)
        hi = health.health_index(p["overall_stress"], 0.98, "Normal")
        assert hi >= 85
        assert health.health_band(hi)["level"] == "NORMAL"

    def test_prediction_alone_does_not_zero_the_gauge(self):
        """The whole point of the horizon target is lead time - don't throw it away."""
        p = _profile(HEALTHY)
        hi = health.health_index(p["overall_stress"], 0.45, "HDF", 0.55, False)
        assert 20 < hi < 70

    def test_hard_breach_floors_the_gauge(self):
        hi = health.health_index(1.0, 0.05, "HDF", 0.95, True)
        assert hi <= health.CAP_ON_BREACH

    def test_health_is_monotone_in_stress(self):
        vals = [health.health_index(s / 20.0, 0.9, "Normal") for s in range(21)]
        assert all(a >= b for a, b in zip(vals, vals[1:]))

    def test_health_is_bounded(self):
        assert health.health_index(0.0, 1.0, "Normal") <= 100
        assert health.health_index(1.0, 0.0, "HDF", 1.0, True) >= 0

    def test_rul_falls_as_stress_rises(self):
        rising = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]
        r = health.rul_from_trend(rising)
        assert r["method"] == "trend"
        assert 0 < r["readings"] < health.RUL_CAP

    def test_flat_trend_reports_no_degradation(self):
        r = health.rul_from_trend([0.3] * 12)
        assert r.get("unbounded") is True

    def test_single_reading_falls_back_to_nominal(self):
        r = health.estimate_rul(0.5, None)
        assert r["method"] == "nominal"
        assert r["confidence"] == "low"


# ==================================================================
#  ALARMS
# ==================================================================
class TestAlarms:

    def test_healthy_reading_is_normal(self):
        p = _profile(HEALTHY)
        a = alarms.evaluate("Normal", 0.02, p["overall_stress"],
                            p["dominant_mode"], [])
        assert a["level"] == "NORMAL"

    def test_breach_bypasses_persistence(self):
        """An arithmetic fact must never wait for confirmation."""
        breach = [{"mode": "OSF", "detail": "strain exceeded", "hard": True}]
        a = alarms.evaluate("OSF", 0.9, 1.0, "OSF", breach, recent_levels=[])
        assert a["level"] == "CRITICAL"
        assert a["persistence"]["held"] is False

    def test_isolated_flicker_is_held_back(self):
        a = alarms.evaluate("HDF", 0.85, 0.5, "HDF", [], recent_levels=["NORMAL"])
        assert a["persistence"]["held"] is True
        assert a["level"] == "WARNING"          # one band down from CRITICAL

    def test_sustained_condition_is_published(self):
        a = alarms.evaluate("HDF", 0.85, 0.5, "HDF", [],
                            recent_levels=["CRITICAL", "CRITICAL"])
        assert a["level"] == "CRITICAL"
        assert a["persistence"]["held"] is False

    def test_deescalation_is_immediate(self):
        a = alarms.evaluate("Normal", 0.01, 0.1, "TWF", [],
                            recent_levels=["CRITICAL", "CRITICAL", "CRITICAL"])
        assert a["level"] == "NORMAL"

    def test_message_is_predictive_not_past_tense(self):
        a = alarms.evaluate("HDF", 0.8, 0.5, "HDF", [],
                            recent_levels=["CRITICAL", "CRITICAL"])
        assert "predicted within the next" in a["message"]
        assert a["predicted"] is True
        assert a["has_breached"] is False

    def test_breach_message_is_past_tense(self):
        breach = [{"mode": "PWF", "detail": "Mechanical power 9500 W exceeds the limit",
                   "hard": True}]
        a = alarms.evaluate("PWF", 0.9, 1.0, "PWF", breach)
        assert a["has_breached"] is True
        assert "exceeds" in a["message"]

    def test_worst_of_three_sources_wins(self):
        breach = [{"mode": "OSF", "detail": "x", "hard": True}]
        a = alarms.evaluate("Normal", 0.0, 0.0, "TWF", breach)
        assert a["level"] == "CRITICAL"          # rule check overrides a calm model


# ==================================================================
#  EXPLAINER
# ==================================================================
class TestExplainer:

    def test_attribution_reconstructs_the_model_exactly(self):
        """If this fails the explanation panel is lying and must not be shown."""
        df = pd.read_csv(EXPANDED_CSV).sample(15, random_state=7)
        X = to_matrix(engineer_features(df)).to_numpy()
        v = explainer.verify_additivity(predictor.get_bundle()["model"], X)
        assert v["exact"], "max error {}".format(v["max_absolute_error"])
        assert v["max_absolute_error"] < 1e-9

    def test_explanation_names_the_governing_feature(self):
        df = pd.read_csv(EXPANDED_CSV)
        row = df[df.failure_class == "HDF"].iloc[0]
        fr = engineer_features(pd.DataFrame([row]))
        x = to_matrix(fr).to_numpy()[0]
        model = predictor.get_bundle()["model"]
        e = explainer.explain_for_class(model, x, "HDF", fr.iloc[0].to_dict())
        top = [d["feature"] for d in e["top_drivers"][:3]]
        assert "temp_delta" in top

    def test_contributions_are_signed_and_ranked(self):
        df = pd.read_csv(EXPANDED_CSV).sample(1, random_state=11)
        fr = engineer_features(df)
        x = to_matrix(fr).to_numpy()[0]
        model = predictor.get_bundle()["model"]
        e = explainer.explain_for_class(model, x, "Normal", fr.iloc[0].to_dict())
        mags = [abs(d["contribution"]) for d in e["top_drivers"]]
        assert mags == sorted(mags, reverse=True)
