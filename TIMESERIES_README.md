# Time-Series Power Flow Module

`timeseries.py` extends the base power-flow solver to run repeated Newton-Raphson solves across time steps. At each step the loads in the circuit are scaled by per-load modifier values read from a CSV profile, the solver runs, and the bus voltages and angles are recorded. The original load values are restored after the full simulation.

---

## Input: Load Modifier CSV

The profile CSV must have one row per time step. It requires:

| Column | Role |
|---|---|
| **Step column** (e.g. `time`) | Identifies each time step in the output. Can be any label; set `step_column=None` to use the row index instead. |
| **One modifier column per load** | A multiplier applied to that load's base MW and MVAR at each step. Must be ≥ 0. |

The modifier is a **scale factor relative to the load's base values** defined in the circuit. A value of `1.0` means no change; `0.5` halves the load; `1.2` increases it by 20%.

### Example — two loads with independent profiles

```csv
time,LD2_scale,LD3_scale
1,1.0,0.8
2,0.5,1.0
3,0.75,1.2
4,1.0,0.9
```

If the circuit defines `LD2` with 100 MW / 50 MVAR and `LD3` with 60 MW / 30 MVAR, then at step 3:

- `LD2` → 75 MW / 37.5 MVAR (`0.75 × base`)
- `LD3` → 72 MW / 36 MVAR (`1.2 × base`)

### Example — same modifier applied to multiple loads

If two loads should scale together, duplicate the column value in the CSV:

```csv
time,LD2_scale,LD3_scale
1,1.0,1.0
2,0.5,0.5
3,0.75,0.75
```

Then map both columns to their respective loads (see usage below).

---

## Usage

```python
from circuit import Circuit
from timeseries import TimeSeriesPowerFlow

# 1. Build and solve the base circuit (calc_ybus must be called first)
circuit = Circuit("My System")
# ... add buses, lines, generators, loads ...
circuit.calc_ybus()

# 2. Create the time-series runner
ts = TimeSeriesPowerFlow()

# 3. Load the profile CSV
#    step_column: name of the column to use as the step label in results.
#    Pass step_column=None to use the row index.
ts.load_profile("profile.csv", step_column="time")

# 4. Map modifier columns to load names
#    Key   = column name in the CSV
#    Value = load name in the circuit
ts.assign_per_load_modifiers({
    "LD2_scale": "LD2",
    "LD3_scale": "LD3",
})

# 5. Run the simulation
results = ts.run(circuit)

# 6. (Optional) Save results to CSV
ts.save_results_csv("timeseries_results.csv")
```

### Method reference

| Method | Description |
|---|---|
| `load_profile(csv_path, step_column="time")` | Reads the CSV and stores the profile. Raises `FileNotFoundError` if the file is missing and `ValueError` if `step_column` is not a column in the file. |
| `assign_per_load_modifiers(column_to_load)` | Maps CSV columns to circuit load names. Keys and values are stripped of whitespace. Raises `ValueError` for an empty mapping or blank strings. |
| `run(circuit, ybus=None, tol=1e-3, max_iter=50)` | Executes the simulation and returns a `pd.DataFrame`. Raises `ValueError` if no profile or assignment is configured. Loads are restored to their base values after the run. |
| `save_results_csv(output_path)` | Writes `results` to CSV. Raises `ValueError` if `run()` has not been called yet. |

---

## Output

`run()` returns a `pd.DataFrame` with one row per time step and the following columns:

| Column | Type | Description |
|---|---|---|
| `step` | any | Value from the step column (or row index if `step_column=None`) |
| `modifier_<load_name>` | float | The scale factor applied to that load at this step |
| `V_<bus_name>_pu` | float | Bus voltage magnitude in per-unit |
| `angle_<bus_name>_deg` | float | Bus voltage angle in degrees |
| `converged` | bool | Whether the Newton-Raphson solver converged |
| `iterations` | int | Number of solver iterations used |
| `max_mismatch` | float | Final power mismatch (last entry of mismatch history); `NaN` if unavailable |

### Example output (two-bus system, four steps)

| step | modifier_LD2 | V_One_pu | V_Two_pu | angle_One_deg | angle_Two_deg | converged | iterations | max_mismatch |
|---|---|---|---|---|---|---|---|---|
| 1 | 1.00 | 1.0000 | 0.9724 | 0.0 | -2.87 | True | 4 | 8.1e-07 |
| 2 | 0.50 | 1.0000 | 0.9862 | 0.0 | -1.43 | True | 3 | 2.0e-07 |
| 3 | 0.75 | 1.0000 | 0.9793 | 0.0 | -2.15 | True | 4 | 4.9e-07 |
| 4 | 1.00 | 1.0000 | 0.9724 | 0.0 | -2.87 | True | 4 | 8.1e-07 |

The `results` DataFrame is also stored as `ts.results` after the run.

---

## Standalone Example Script

For a minimal end-to-end example, run `timeseries_main.py` from the repository root:

```python
PYTHONPATH=. .venv/bin/python timeseries_main.py
```

This script builds the simple two-bus time-series system used in the tests, writes an input profile CSV with the load scale sequence `1.0, 0.75, 0.5, 0.75, 1.0`, runs the study, prints the Y-bus and full time-series results, and saves:

- `timeseries_input.csv`
- `timeseries_output.csv`

The generated input profile has this form:

```csv
time,LD2_scale
1,1.0
2,0.75
3,0.5
4,0.75
5,1.0
```
