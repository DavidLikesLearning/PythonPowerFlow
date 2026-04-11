import numpy as np

from bus import BusType
from circuit import Circuit
from powerflow import PowerFlow


def build_example_5bus() -> Circuit:
    """Build the same 5-bus Example 6.9 network used in test_powerflow."""
    circuit = Circuit("5-Bus Example 6.9")

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

    circuit.add_generator("G1", "One", voltage_setpoint=1.0, mw_setpoint=278.3)
    circuit.add_load("LD2", "Two", mw=800.0, mvar=280.0)
    circuit.add_load("LD3", "Three", mw=80.0, mvar=40.0)
    circuit.add_generator("G3", "Three", voltage_setpoint=1.05, mw_setpoint=520.0)

    circuit.calc_ybus()
    return circuit


def print_heading(title: str) -> None:
    print(f"\n{'=' * 80}")
    print(title)
    print(f"{'=' * 80}")


def print_solve_results(results: dict) -> None:
    """Print every field returned by PowerFlow.solve() in a readable format."""
    print_heading("PowerFlow.solve() Output")
    for key, value in results.items():
        print(f"{key}:")
        if isinstance(value, np.ndarray):
            print(np.array2string(value, precision=6, suppress_small=False))
        else:
            print(value)
        print()


def print_bus_summary(circuit: Circuit, results: dict, ybus_np: np.ndarray) -> None:
    """Print solved bus quantities bus-by-bus for quick inspection."""
    pf = PowerFlow()
    p_calc, q_calc = pf._calc_power_injections(
        ybus_np,
        results["angles_rad"],
        results["voltages"],
    )

    print_heading("Solved Bus Summary")
    for index, bus_name in enumerate(results["bus_names"]):
        print(
            f"{bus_name:>5} | "
            f"V={results['voltages'][index]:.5f} pu | "
            f"angle={results['angles_deg'][index]:.5f} deg | "
            f"P={p_calc[index]:.5f} pu | "
            f"Q={q_calc[index]:.5f} pu"
        )


def main() -> None:
    np.set_printoptions(precision=6, suppress=True)

    print_heading("Building 5-Bus Example 6.9")
    circuit = build_example_5bus()
    ybus_np = circuit.y_bus.values

    print(circuit)
    print()
    print("Bus order:", list(circuit.buses.keys()))

    print_heading("Y-Bus Matrix")
    print(circuit.y_bus)

    print_heading("Running Newton-Raphson Power Flow")
    pf = PowerFlow()
    results = pf.solve(circuit, ybus_np, tol=1e-3, max_iter=50)

    print_solve_results(results)
    print_bus_summary(circuit, results, ybus_np)


if __name__ == "__main__":
    main()