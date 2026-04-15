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


def _build_five_bus_fault_system_no_subtransient() -> Circuit:
    """Build the same 5-bus network used by power-flow tests with default generator X'' values."""
    circuit = Circuit("5-Bus Example 6.9 Fault Study")

    circuit.add_bus("One", 15.0, bus_type=BusType.Slack)
    circuit.add_bus("Two", 345.0, bus_type=BusType.PQ)
    circuit.add_bus("Three", 15.0, bus_type=BusType.PV)
    circuit.add_bus("Four", 345.0, bus_type=BusType.PQ)
    circuit.add_bus("Five", 345.0, bus_type=BusType.PQ)

    circuit.add_transmission_line("L42", "Four", "Two", r=0.009, x=0.1, b=1.72)
    circuit.add_transmission_line("L52", "Five", "Two", r=0.0045, x=0.05, b=0.88)
    circuit.add_transmission_line("L54", "Five", "Four", r=0.00225, x=0.025, b=0.44)
    circuit.add_transformer("T15", "One", "Five", r=0.0015, x=0.02)
    circuit.add_transformer("T34", "Three", "Four", r=0.00075, x=0.01)

    # Intentionally omit x_subtransient so generators use default None.
    circuit.add_generator("G1", "One", voltage_setpoint=1.0, mw_setpoint=278.3)
    circuit.add_load("LD2", "Two", mw=800.0, mvar=280.0)
    circuit.add_load("LD3", "Three", mw=80.0, mvar=40.0)
    circuit.add_generator("G3", "Three", voltage_setpoint=1.05, mw_setpoint=520.0)

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
    assert abs(result["ifn_pu"] - abs(result["ifn"])) < 1e-12

    for k, bus_name in enumerate(["One", "Two"]):
        zkn = zbus_fault[k, 1]
        expected_ek = (1.0 - zkn / znn) * (1.0 + 0.0j)
        assert abs(result["post_fault_bus_voltages"][bus_name] - abs(expected_ek)) < 1e-12


def test_simulate_symmetrical_fault_custom_prefault_voltage():
    circuit = _build_two_bus_fault_system()
    study = FaultStudy()

    vf = 0.98 + 0.02j
    result = study.solve(circuit, vf=vf, fault_bus_name="Two")

    znn = result["zbus_fault"].to_numpy(dtype=np.complex128)[1, 1]
    assert abs(result["ifn"] - (vf / znn)) < 1e-12
    assert abs(result["ifn_pu"] - abs(result["ifn"])) < 1e-12


def test_fault_study_does_not_mutate_circuit_ybus():
    circuit = _build_two_bus_fault_system()
    study = FaultStudy()

    y_before = circuit.y_bus.copy(deep=True)
    _ = study.solve(circuit, fault_bus_name="Two")
    y_after = circuit.y_bus

    assert np.allclose(y_before.values, y_after.values)


def test_fault_study_requires_generator_subtransient_reactance():
    circuit = _build_two_bus_fault_system()
    circuit.generators["G1"].x_subtransient = None
    study = FaultStudy()

    # With no subtransient reactance, no Norton shunt is added.
    y_fault = study._calc_ybus_fault(circuit)
    assert np.allclose(y_fault.values, circuit.y_bus.values)

    # Two-bus series-only network is singular without generator shunt support.
    try:
        study.solve(circuit, fault_bus_name="One")
        assert False, "Expected ValueError for singular Y-bus when x_subtransient is missing"
    except ValueError as exc:
        assert "singular" in str(exc)


def test_fault_study_rejects_unknown_fault_bus_name():
    circuit = _build_two_bus_fault_system()
    study = FaultStudy()

    try:
        study.solve(circuit, fault_bus_name="MissingBus")
        assert False, "Expected ValueError for unknown fault bus"
    except ValueError as exc:
        assert "fault_bus_name" in str(exc)


def test_five_bus_fault_study_no_subtransient_print_ybus_and_bus1_fault_results():
    circuit = _build_five_bus_fault_system_no_subtransient()
    study = FaultStudy()

    ybus_fault = study._calc_ybus_fault(circuit)
    print("\n=== 5-Bus ybus_fault (no generator subtransient reactances) ===")
    print(ybus_fault)

    result = study.solve(circuit, fault_bus_name="One")

    print("\n=== 5-Bus solid fault at Bus One ===")
    print(f"Fault current Ifn: {result['ifn']}")
    print(f"Fault current magnitude |Ifn| (pu): {result['ifn_pu']}")
    print("Post-fault bus voltage magnitudes (pu):")
    for bus_name, voltage in result["post_fault_bus_voltages"].items():
        print(f"  {bus_name}: {voltage}")

    assert result["fault_bus_name"] == "One"
    assert "ifn" in result
    assert "ifn_pu" in result
    assert len(result["post_fault_bus_voltages"]) == len(circuit.buses)
