import numpy as np

from bus import BusType
from circuit import Circuit
from faultstudy import FaultStudy


def _build_two_bus_fault_system() -> Circuit:
    circuit = Circuit("Fault Test")
    circuit.add_bus("One", 230.0, bus_type=BusType.Slack)
    circuit.add_bus("Two", 230.0, bus_type=BusType.PQ)

    # A series line alone gives a singular Y-bus; generator Norton shunt makes
    # the fault Y-bus invertible.
    circuit.add_transmission_line("L12", "One", "Two", r=0.0, x=0.2)
    circuit.add_generator(
        "G1",
        "One",
        voltage_setpoint=1.0,
        mw_setpoint=100.0,
        x_subtransient=0.25,
    )
    circuit.calc_ybus()
    return circuit


def test_calc_ybus_fault_adds_generator_norton_shunt():
    circuit = _build_two_bus_fault_system()
    study = FaultStudy()

    y_base = circuit.y_bus.to_numpy(dtype=np.complex128)
    y_fault = study._calc_ybus_fault(circuit).to_numpy(dtype=np.complex128)

    expected_delta = 1.0 / (1j * 0.25)
    delta_11 = y_fault[0, 0] - y_base[0, 0]
    assert abs(delta_11 - expected_delta) < 1e-12
    assert abs(y_fault[0, 1] - y_base[0, 1]) < 1e-12
    assert abs(y_fault[1, 0] - y_base[1, 0]) < 1e-12
    assert abs(y_fault[1, 1] - y_base[1, 1]) < 1e-12


def test_simulate_symmetrical_fault_uses_znn_and_zkn_formulae():
    circuit = _build_two_bus_fault_system()
    study = FaultStudy()

    result = study.solve(circuit, fault_bus_name="Two")
    zbus_fault = result["zbus_fault"].to_numpy(dtype=np.complex128)

    znn = zbus_fault[1, 1]
    assert abs(result["ifn"] - ((1.0 + 0.0j) / znn)) < 1e-12

    for k, bus_name in enumerate(["One", "Two"]):
        zkn = zbus_fault[k, 1]
        expected_ek = (1.0 - zkn / znn) * (1.0 + 0.0j)
        assert abs(result["post_fault_bus_voltages"][bus_name] - expected_ek) < 1e-12


def test_simulate_symmetrical_fault_custom_prefault_voltage():
    circuit = _build_two_bus_fault_system()
    study = FaultStudy()

    vf = 0.98 + 0.02j
    result = study.solve(circuit, vf=vf, fault_bus_name="Two")

    znn = result["zbus_fault"].to_numpy(dtype=np.complex128)[1, 1]
    assert abs(result["ifn"] - (vf / znn)) < 1e-12


def test_fault_study_does_not_mutate_circuit_ybus():
    circuit = _build_two_bus_fault_system()
    study = FaultStudy()

    y_before = circuit.y_bus.copy(deep=True)
    _ = study.solve(circuit, fault_bus_name="Two")
    y_after = circuit.y_bus

    assert np.allclose(y_before.values, y_after.values)


def test_fault_study_requires_generator_subtransient_reactance():
    circuit = Circuit("Fault Missing Xpp")
    circuit.add_bus("One", 230.0, bus_type=BusType.Slack)
    circuit.add_generator("G1", "One", voltage_setpoint=1.0, mw_setpoint=100.0)
    circuit.calc_ybus()

    study = FaultStudy()

    try:
        study.solve(circuit, fault_bus_name="One")
        assert False, "Expected ValueError for missing x_subtransient"
    except ValueError as exc:
        assert "missing x_subtransient" in str(exc)


def test_fault_study_rejects_unknown_fault_bus_name():
    circuit = _build_two_bus_fault_system()
    study = FaultStudy()

    try:
        study.solve(circuit, fault_bus_name="MissingBus")
        assert False, "Expected ValueError for unknown fault bus"
    except ValueError as exc:
        assert "fault_bus_name" in str(exc)
