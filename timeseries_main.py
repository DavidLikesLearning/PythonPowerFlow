from pathlib import Path

import pandas as pd

from bus import BusType
from circuit import Circuit
from timeseries import TimeSeriesPowerFlow


LOAD_SCALES = [1.0, 0.75, 0.5, 0.75, 1.0]
INPUT_CSV = Path("timeseries_input.csv")
OUTPUT_CSV = Path("timeseries_output.csv")


def build_two_bus_timeseries_system() -> Circuit:
    circuit = Circuit("Time Series Two-Bus Example")
    circuit.add_bus("One", 230.0, bus_type=BusType.Slack)
    circuit.add_bus("Two", 230.0, bus_type=BusType.PQ)

    circuit.add_transmission_line("L12", "One", "Two", r=0.0, x=0.2)
    circuit.add_generator("G1", "One", voltage_setpoint=1.0, mw_setpoint=200.0)
    circuit.add_load("LD2", "Two", mw=100.0, mvar=50.0)
    circuit.calc_ybus()
    return circuit


def build_profile_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": [1, 2, 3, 4, 5],
            "LD2_scale": LOAD_SCALES,
        }
    )


def write_profile_csv(profile: pd.DataFrame, output_path: Path) -> Path:
    profile.to_csv(output_path, index=False)
    return output_path


def main() -> None:
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", None)
    pd.set_option("display.precision", 4)

    circuit = build_two_bus_timeseries_system()
    profile = build_profile_dataframe()
    input_path = write_profile_csv(profile, INPUT_CSV)

    ts = TimeSeriesPowerFlow()
    ts.load_profile(input_path, step_column="time")
    ts.assign_per_load_modifiers({"LD2_scale": "LD2"})
    results = ts.run(circuit)
    output_path = ts.save_results_csv(OUTPUT_CSV)

    print("Two-bus time-series example")
    print()
    print("Y-Bus matrix:")
    print(circuit.y_bus)
    print()
    print(f"Input profile CSV: {input_path.resolve()}")
    print(profile)
    print()
    print("Time-series results:")
    print(results)
    print()
    print(f"Output results CSV: {output_path.resolve()}")


if __name__ == "__main__":
    main()