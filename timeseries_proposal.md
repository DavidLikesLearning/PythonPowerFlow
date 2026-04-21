# Time-Series Power Flow Enhancement Proposal

## 1. Purpose

This proposal describes an enhancement to add time-series simulation capability on top of the existing steady-state Newton-Raphson power flow solver.

The enhancement allows a user to:

- Provide a CSV containing time steps (or index) and load modifiers.
- Map modifier columns to one or more named loads in the network model.
- Run one power flow solve per time step.
- Aggregate bus voltage and angle results into a single tabular output.
- Optionally export results to CSV for post-processing and plotting.

## 2. Problem Statement

The current solver computes a single operating point for one set of static inputs. Practical studies often require observing how bus voltages and angles evolve as load changes over time. Without a time-series layer, users must manually repeat model edits and solves for each time step, which is error-prone and difficult to validate.

## 3. Goals and Non-Goals

### Goals

- Reuse existing power flow solver logic without modifying solver math.
- Provide a clean API for loading time-profile data from CSV.
- Support both:
  - One shared modifier column mapped to multiple loads.
  - Per-load modifier columns mapped explicitly.
- Return a unified pandas DataFrame with time-indexed results.
- Support CSV export of final results.
- Preserve circuit integrity by restoring original load values after simulation.

### Non-Goals (MVP)

- Generator dispatch time profiles.
- Tap-changing transformer controls.
- Contingency switching per time step.
- Parallel/distributed simulation execution.
- Built-in plotting utilities.

## 4. Proposed Architecture

## 4.1 High-Level Design

Add a new module dedicated to orchestration logic:

- `timeseries.py`
  - Owns profile parsing, assignment mapping, per-step load updates, repeated solver calls, and result aggregation.

Keep these modules unchanged (or minimally touched only for compatibility):

- `powerflow.py`: steady-state solver used as execution engine.
- `circuit.py`: data container for buses, loads, generators, and Y-bus.
- `load.py`: source of MW/MVAr and per-unit conversion.

## 4.2 Component Responsibilities

### TimeSeriesPowerFlow (new orchestration class)

Responsibilities:

- Load profile CSV and validate required columns.
- Configure modifier-to-load assignment rules.
- Snapshot baseline load values.
- For each time step:
  - Apply modifiers to target loads.
  - Invoke `PowerFlow.solve(...)`.
  - Capture bus voltages and angles.
  - Capture solve metadata (converged, iterations, mismatch).
- Restore baseline load values after run completion.
- Return and optionally persist output DataFrame.

### AssignmentConfig (lightweight config model)

Encapsulates mapping mode:

- Shared mode: one modifier column applied to a list of load names.
- Per-load mode: each modifier column maps to a specific load name.

## 4.3 Data Flow

1. User loads profile CSV.
2. User defines assignment mapping.
3. Runner validates:
   - Profile columns.
   - Assigned load names exist in circuit.
   - Modifiers are numeric and non-negative.
4. Runner loops over rows:
   - Computes step load values from baseline × modifier.
   - Executes one power flow solve.
   - Appends structured row to result list.
5. Runner builds pandas DataFrame and returns it.
6. Optional write to CSV.

## 5. Input and Output Specifications

## 5.1 Input CSV Formats

### Shared modifier format

```csv
time,load
1,1.0
2,0.5
3,0.75
4,1.0
```

Interpretation:

- A single profile column (`load`) scales all assigned loads.

### Per-load modifier format

```csv
time,LD2_scale,LD3_scale
1,1.0,1.0
2,0.8,0.9
3,1.1,0.7
4,1.0,1.0
```

Interpretation:

- Each modifier column is mapped independently to a specific load.

## 5.2 Load Scaling Rule

For each assigned load and each time step:

- `MW_step = MW_base * modifier`
- `MVAr_step = MVAr_base * modifier`

Both real and reactive powers scale by the same factor in MVP.

## 5.3 Output DataFrame Schema

Suggested columns:

- `step` (time or index)
- `modifier_<LoadName>` for each assigned load
- `V_<BusName>_pu` for each bus
- `angle_<BusName>_deg` for each bus
- `converged`
- `iterations`
- `max_mismatch`

This structure is intentionally flat for easy CSV export and plotting.

## 6. Implementation Plan

## Phase 1: Module Skeleton

- Add `timeseries.py` with:
  - Assignment config object.
  - `load_profile(...)`.
  - Assignment methods.
  - `run(...)` orchestration.
  - `save_results_csv(...)`.

## Phase 2: Validation and Error Handling

- Validate profile column availability.
- Validate load-name existence.
- Validate numeric modifiers and non-negative range.
- Provide clear error messages identifying bad column, bad load, or bad value.

## Phase 3: Result Modeling

- Standardize output naming conventions.
- Include solver metadata to detect problematic steps.
- Ensure deterministic row ordering by profile order.

## Phase 4: Integration and Usability

- Add optional helper example in main flow (or dedicated demo script).
- Add minimal user docs with CSV examples and mapping examples.

## 7. Testing Strategy

## 7.1 Unit Tests (module behavior)

- CSV load succeeds with valid file.
- Missing file raises `FileNotFoundError`.
- Missing step column raises `ValueError`.
- Empty assignment raises `ValueError`.
- Invalid load mapping raises `ValueError`.
- Negative modifiers raise `ValueError`.
- Result export creates expected CSV.

## 7.2 Functional Tests (solver integration)

- Build small deterministic network (e.g., 2-bus).
- Apply changing load profile.
- Assert that at least one bus voltage changes across steps.
- Assert row count equals number of time steps.
- Assert returned columns include all buses and metadata fields.

## 7.3 Regression Tests

- Fixed profile + fixed network should reproduce same output across runs.
- Snapshot selected values with tolerance to catch unintended behavior drift.

## 8. Validation Against PowerWorld Time-Series Examples

## 8.1 Validation Objective

Demonstrate that the enhancement produces time-series voltage/angle trajectories consistent with PowerWorld for equivalent network and load profiles.

## 8.2 Alignment Requirements

Before comparing results, ensure both tools share:

- Same network topology and per-unit base.
- Same line/transformer/generator/load parameters.
- Same slack/PV/PQ bus assignments.
- Same load profile per step.
- Same convergence tolerances where possible.

## 8.3 Comparison Procedure

1. Build identical test case in both environments (recommended: 5-bus benchmark).
2. Apply identical time-series load multipliers.
3. Export per-step bus voltage magnitudes and angles from both tools.
4. Join datasets on `(step, bus)`.
5. Compute error metrics:
   - Absolute voltage error: `|V_py - V_pw|`
   - Absolute angle error: `|theta_py - theta_pw|`
   - Optional RMS errors across all steps and buses.
6. Flag steps exceeding thresholds.

## 8.4 Suggested Acceptance Criteria

- Voltage magnitude max absolute error <= 1e-3 pu.
- Angle max absolute error <= 0.05 deg.
- No systematic drift trend across time steps.
- Convergence statuses match for all valid steps.

## 8.5 Edge-Case Validation Matrix

Include PowerWorld comparison for:

- Flat profile (all modifiers 1.0).
- Light-to-heavy load ramp.
- Oscillating profile (up/down changes).
- Multi-load independent profiles.
- Near-stressed operating points (high loading).

## 9. Risks and Mitigations

- Risk: Profile contains invalid or missing numeric values.
  - Mitigation: strict validation with explicit error messages.

- Risk: Non-convergent steps produce incomplete outputs.
  - Mitigation: include `converged` and `max_mismatch` columns per step.

- Risk: Cumulative load mutation across steps.
  - Mitigation: always scale from baseline snapshot; restore at end.

- Risk: Differences vs PowerWorld due to modeling assumptions.
  - Mitigation: document assumptions, align solver settings, and compare with tolerance bands.

## 10. Future Enhancements

- Warm-start option (use previous step voltages/angles as initial conditions).
- Time-series generator dispatch and voltage setpoint profiles.
- Built-in plotting helpers for selected buses.
- Scenario batching and parallel execution.
- Enhanced reporting (summary stats, worst-step diagnostics).

## 11. Conclusion

This enhancement introduces a clear, modular time-series execution layer that reuses the existing power flow solver and exposes outputs in an analysis-ready pandas DataFrame. The architecture is intentionally incremental: easy to test, easy to validate against PowerWorld, and extensible for future operational studies.
