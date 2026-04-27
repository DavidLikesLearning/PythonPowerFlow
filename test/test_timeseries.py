import numpy as np
import pandas as pd
import pytest
from pathlib import Path

from bus import BusType
from circuit import Circuit
from timeseries import TimeSeriesPowerFlow


def _build_two_bus_timeseries_system() -> Circuit:
    circuit = Circuit("Time Series Test")
    circuit.add_bus("One", 230.0, bus_type=BusType.Slack)
    circuit.add_bus("Two", 230.0, bus_type=BusType.PQ)

    circuit.add_transmission_line("L12", "One", "Two", r=0.0, x=0.2)
    circuit.add_generator("G1", "One", voltage_setpoint=1.0, mw_setpoint=200.0)
    circuit.add_load("LD2", "Two", mw=100.0, mvar=50.0)
    circuit.calc_ybus()
    return circuit


def test_timeseries_per_load_modifier_runs_and_aggregates(tmp_path):
    csv_path = tmp_path / "profile.csv"
    csv_path.write_text("time,LD2_scale\n1,1.0\n2,0.5\n3,0.75\n4,1.0\n", encoding="utf-8")

    circuit = _build_two_bus_timeseries_system()
    ts = TimeSeriesPowerFlow()
    ts.load_profile(csv_path, step_column="time")
    ts.assign_per_load_modifiers({"LD2_scale": "LD2"})
    results = ts.run(circuit)

    assert len(results) == 4
    assert "step" in results.columns
    assert "modifier_LD2" in results.columns
    assert "V_One_pu" in results.columns
    assert "V_Two_pu" in results.columns
    assert "angle_One_deg" in results.columns
    assert "angle_Two_deg" in results.columns
    assert "converged" in results.columns

    # The load modifier changes over time, so voltage should not be constant.
    assert results["V_Two_pu"].nunique() > 1


def test_timeseries_save_results_csv(tmp_path):
    csv_path = tmp_path / "profile.csv"
    csv_path.write_text("time,LD2_scale\n1,1.0\n2,0.5\n", encoding="utf-8")

    circuit = _build_two_bus_timeseries_system()
    ts = TimeSeriesPowerFlow()
    ts.load_profile(csv_path, step_column="time")
    ts.assign_per_load_modifiers({"LD2_scale": "LD2"})
    results = ts.run(circuit)

    out_path = tmp_path / "timeseries_results.csv"
    saved_path = ts.save_results_csv(out_path)

    assert saved_path.exists()
    reloaded = pd.read_csv(saved_path)
    assert len(reloaded) == len(results)


def test_timeseries_per_load_modifier_mapping(tmp_path):
    csv_path = tmp_path / "profile_multi.csv"
    csv_path.write_text(
        "time,LD2_scale\n1,1.0\n2,0.8\n3,1.2\n",
        encoding="utf-8",
    )

    circuit = _build_two_bus_timeseries_system()
    ts = TimeSeriesPowerFlow()
    ts.load_profile(csv_path, step_column="time")
    ts.assign_per_load_modifiers({"LD2_scale": "LD2"})
    results = ts.run(circuit)

    assert len(results) == 3
    assert "modifier_LD2" in results.columns
    assert list(results["modifier_LD2"]) == [1.0, 0.8, 1.2]


# ---------------------------------------------------------------------------
# PowerWorld / reference validation
# ---------------------------------------------------------------------------
# Place two files in test/fixtures/ to enable this test:
#   timeseries_profile.csv          — the load modifier profile (same format as
#                                     the module's input CSV, e.g. time,LD2_scale)
#   timeseries_expected_results.csv — reference results from PowerWorld or
#                                     another validated source
#
# Expected results CSV columns (one per bus per quantity):
#   step, V_<bus_name>_pu, angle_<bus_name>_deg
#
# Example:
#   step,V_One_pu,V_Two_pu,angle_One_deg,angle_Two_deg
#   1,1.0000,0.9724,0.000,-2.874
#   2,1.0000,0.9862,0.000,-1.432
# ---------------------------------------------------------------------------

_FIXTURES = Path(__file__).parent / "fixtures"
_PROFILE_CSV = _FIXTURES / "timeseries_profile.csv"
_EXPECTED_CSV = _FIXTURES / "timeseries_expected_results.csv"

_VOLTAGE_TOL = 1e-3   # per-unit
_ANGLE_TOL = 1e-2     # degrees


@pytest.mark.skipif(
    not (_PROFILE_CSV.exists() and _EXPECTED_CSV.exists()),
    reason=(
        "Validation fixtures not found. "
        "Provide test/fixtures/timeseries_profile.csv and "
        "test/fixtures/timeseries_expected_results.csv to enable this test."
    ),
)
def test_timeseries_voltages_angles_against_reference():
    """
    Compare simulated bus voltages and angles step-by-step against a
    reference CSV (e.g. a PowerWorld export).

    Tolerances:
        Voltage : ±1e-3 pu
        Angle   : ±1e-2 degrees
    """
    expected = pd.read_csv(_EXPECTED_CSV)

    profile_df = pd.read_csv(_PROFILE_CSV)
    profile_df.columns = [str(c).strip() for c in profile_df.columns]
    step_col = profile_df.columns[0]
    modifier_cols = [c for c in profile_df.columns if c != step_col]

    # Modifier columns are expected to follow <load_name>_scale convention.
    # Edit this mapping if your fixture uses different column names.
    circuit = _build_two_bus_timeseries_system()
    column_to_load = {
        col: col if col in circuit.loads else col.replace("_scale", "")
        for col in modifier_cols
    }

    ts = TimeSeriesPowerFlow()
    ts.load_profile(_PROFILE_CSV, step_column=step_col)
    ts.assign_per_load_modifiers(column_to_load)
    results = ts.run(circuit)

    assert len(results) == len(expected), (
        f"Row count mismatch: simulated {len(results)} steps, "
        f"reference has {len(expected)} steps."
    )

    voltage_cols = [c for c in expected.columns if c.startswith("V_") and c.endswith("_pu")]
    angle_cols = [c for c in expected.columns if c.startswith("angle_") and c.endswith("_deg")]

    missing = [c for c in voltage_cols + angle_cols if c not in results.columns]
    assert not missing, f"Simulated results are missing columns present in reference: {missing}"

    for col in voltage_cols:
        np.testing.assert_allclose(
            results[col].to_numpy(),
            expected[col].to_numpy(),
            atol=_VOLTAGE_TOL,
            rtol=0,
            err_msg=f"Voltage mismatch in '{col}'",
        )

    for col in angle_cols:
        np.testing.assert_allclose(
            results[col].to_numpy(),
            expected[col].to_numpy(),
            atol=_ANGLE_TOL,
            rtol=0,
            err_msg=f"Angle mismatch in '{col}'",
        )
