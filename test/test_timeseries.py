import pandas as pd

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


def test_timeseries_shared_modifier_runs_and_aggregates(tmp_path):
    csv_path = tmp_path / "profile.csv"
    csv_path.write_text("time,load\n1,1.0\n2,0.5\n3,0.75\n4,1.0\n", encoding="utf-8")

    circuit = _build_two_bus_timeseries_system()
    ts = TimeSeriesPowerFlow()
    ts.load_profile(csv_path, step_column="time")
    ts.assign_shared_modifier(load_names=["LD2"], modifier_column="load")
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
    csv_path.write_text("time,load\n1,1.0\n2,0.5\n", encoding="utf-8")

    circuit = _build_two_bus_timeseries_system()
    ts = TimeSeriesPowerFlow()
    ts.load_profile(csv_path, step_column="time")
    ts.assign_shared_modifier(load_names=["LD2"], modifier_column="load")
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
