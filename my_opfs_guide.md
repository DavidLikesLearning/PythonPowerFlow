# my_opfs.py — Usage Guide

Interactive terminal tool for comparing AC SOCP, DC OPF, and pandapower solvers on standard power-flow test cases.

## Quick start

```bash
python my_opfs.py
```

Press **Ctrl-C** at any prompt to exit cleanly.

---

## Session walkthrough

The tool walks you through six steps.  All heavy solver imports happen *after* the prompts, so the menu appears instantly.

### Step 1 — SOCP mode  (pick one)

| Choice | What it does |
|--------|--------------|
| 1. SOCP-PF | Fixes generator MW dispatch; compares SOCP voltages to pandapower NR as ground truth |
| 2. SOCP-OPF | Minimises total generation cost; use this to study the duality gap |
| 3. Skip SOCP | Hides SOCP column in output (SOCP still runs internally for tightness data) |

### Step 2 — Additional solvers  (comma-separated, or Enter for none)

| # | Solver | Notes |
|---|--------|-------|
| 1 | DC-OPF | Our cvxpy LP; ignores losses and reactive power |
| 2 | PP-NR | pandapower Newton-Raphson AC power flow |
| 3 | PP-DCOPF | pandapower DC OPF (uses 1/x susceptance) |
| 4 | PP-ACOPF | pandapower AC OPF via PYPOWER interior-point (slow) |

### Step 3 — Grid  (pick one)

| # | Grid | Buses | Key property |
|---|------|-------|--------------|
| 1 | IEEE 14-bus | 14 | Meshed; τ≈1 everywhere but loop residuals up to 4.3° |
| 2 | WB5 | 5 | Non-convex bottleneck; SOCP duality gap ≈ 41% |
| 3 | Case22loop (uniform) | 22 | Ring; SOCP exact, zero duality gap |
| 4 | Case22loop (asymmetric) | 22 | Ring with $1/$4 cost split; two local AC optima |

### Step 4 — Generator costs

Default costs are shown.  Enter **Y** to use them or **N** to supply custom values.

**Option a — comma-separated list:**

Enter one number per generator in the order shown, e.g.:

```
> 15, 25, 35, 40, 40
```

**Option b — CSV file:**

The file can be in either of two formats:

*One-column* (costs in generator order, no header):
```
15
25
35
40
40
```

*Two-column* (name,cost — header row optional):
```
gen_name,cost
Gen1,15
Gen2,25
Gen3,35
Gen6,40
Gen8,40
```

### Step 5 — Metrics to display  (comma-separated, or Enter for all)

| # | Metric | Source |
|---|--------|--------|
| 1 | Voltage magnitudes (pu) | `v_mag` per bus |
| 2 | Voltage angles (deg) | `v_ang_deg` per bus |
| 3 | Branch P flows (pu) | `p_fr` per branch, from-end |
| 4 | Branch Q flows (pu) | `q_fr` per branch (zero for DC solvers) |
| 5 | Objective value ($/h) | `details["obj_val"]` |
| 6 | Convergence status | `converged` |
| 7 | Solve time (s) | `details["solve_time_s"]` |
| 8 | SOCP tightness τ | τ = \|W_ij\|² / (W_ii·W_jj) per branch |
| 9 | Loop residuals (deg) | Phase inconsistency around fundamental cycles |

Metrics 8 and 9 are always drawn from the SOCP result, even if SOCP was set to "skip" in Step 1 — a note will say so.

### Step 6 — Save outputs

- **CSV** — the four-section comparison file written by `compare_solvers()`: summary, bus voltages, branch flows, SOCP tightness.  Default filename is `<grid>_comparison.csv`.
- **Plots** — saves PNG files to the chosen directory:
  - `fig_tightness.png` — per-branch τ bar chart with loop residual annotations
  - `fig_objectives.png` — grouped bar chart of solver costs (OPF grids only)

---

## Example sessions

### Verify SOCP vs NR on IEEE 14-bus

```
Step 1: 1  (SOCP-PF)
Step 2: 2  (PP-NR)
Step 3: 1  (IEEE 14-bus)
Step 4: Y  (default costs)
Step 5: 1,6,7  (voltages, convergence, solve time)
Step 6: N / N  (no save)
```

### Check WB5 duality gap

```
Step 1: 2  (SOCP-OPF)
Step 2: 4  (PP-ACOPF)
Step 3: 2  (WB5)
Step 4: Y
Step 5: 5,8,9  (objective, tightness, loop residuals)
Step 6: Y  wb5_run.csv / N
```

### Run asymmetric ring with custom costs

```
Step 1: 2  (SOCP-OPF)
Step 2: 2,4  (PP-NR, PP-ACOPF)
Step 3: 4  (Case22loop asymmetric)
Step 4: N → b → /path/to/costs.csv
Step 5: (Enter — all metrics)
Step 6: Y  c22_custom.csv / Y  ./plots_out
```

---

## Notes

- **Voltage bounds**: WB5 uses `v_min=0.5, v_max=1.5` automatically (the network's natural operating point is below 0.95 pu).  Case22loop variants use `[0.95, 1.05]`.
- **Bus/branch ordering**: SOCP and DC-OPF columns follow circuit ordering; pandapower columns follow pandapower's internal ordering.  The CSV written by `compare_solvers` aligns all columns to circuit order.
- **PP-NR has no objective value**: metric 5 shows `N/A` for that column.
- **DC Q flows**: metrics 4 shows `[Q=0 DC approx]` annotation on DC-OPF and PP-DCOPF columns.
