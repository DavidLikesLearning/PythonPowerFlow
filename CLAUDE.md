# PythonPowerFlow — OPF Comparison Framework

## Project layout

| File | Role |
|------|------|
| `opfs.py` | Core solvers: AC SOCP, DC OPF, pandapower wrapper, relaxation-gap diagnostics |
| `demo_project.py` | Grid builders, comparison driver, multi-start local-solution demo, per-grid wrappers |
| `plots.py` | Visualization module: 5 publication-ready figures from pre-computed result dicts |
| `my_opfs.py` | Interactive CLI: prompts user to choose solvers, grid, custom costs, metrics, save options |
| `my_opfs_guide.md` | Usage guide for `my_opfs.py`: step-by-step walkthrough, example sessions, CSV format |
| `tests_opfs.py` | 11 pytest tests for SOCP pf and DC OPF on a 3-bus 345 kV network |
| `theory.md` | Full mathematical derivation: AC OPF → lifted W variables → rank-1 → SOC, branch tightness τ, loop residuals, radial exactness theorem, WB5 example, ring operating regimes |
| `socp_proposal.md` | Shorter formulation reference with API table and solver comparison table |
| `references.md` | Annotated bibliography: all sources used in this project with one-line summaries of their specific contribution |

Supporting files from the existing codebase: `circuit.py`, `bus.py`, `settings.py` (provides `grid_settings.sbase`).

---

## Solvers (`opfs.py`)

All three public solvers return the **same dict schema**:

```
source, v_mag, v_ang_deg, p_fr, q_fr, p_to, q_to, converged, details
```

Powers are in **per-unit on `grid_settings.sbase`** (100 MVA by default).

### `solve_socp` — AC SOCP relaxation (Jabr 2006/2007)

**Variables:** `Wd[i] = |V_i|²`, `Wr[k] = Re(V_i V_j*)`, `Wi[k] = Im(V_i V_j*)`, `Pg[g]`, `Qg[g]`

**SOC per branch:**
```
‖[2·Wr[k], 2·Wi[k], Wd[i]−Wd[j]]‖₂ ≤ Wd[i]+Wd[j]
```
Equivalent to `Wr[k]² + Wi[k]² ≤ Wd[i]·Wd[j]` — this is the key relaxation of the rank-1 constraint.

**Modes:**
- `mode="pf"`: fixes `Pg` for all non-slack generators (honours PV setpoints), adds tiny slack-cost to select a unique solution. PV bus voltages are fixed to setpoints.
- `mode="opf"`: minimises `cost @ Pg`. PV bus voltages are **free** within `[v_min, v_max]` — do NOT fix them in opf mode (see bugs section).

**Solver cascade:** tries CLARABEL → GUROBI → SCS; returns `converged=False` if all fail.

**`details` dict exposes lifted W variables:**
```python
details["Wd"], details["Wr"], details["Wi"]   # for relaxation-gap analysis
```

### `solve_dc_opf` — Linear DC OPF (LP)

Standard lossless DC approximation: `V ≡ 1 pu`, angles only.

`B_DC` uses `b_ij = x/(r²+x²) = Im(y_series)` — matches pandapower's internal DC model for low r/x lines. Note: for high r/x lines (e.g. WB5) there is a discrepancy vs. pandapower's `1/x` approximation.

`q_fr`, `q_to` are returned as zero arrays.

### `solve_pandapower` — pandapower wrapper

**Modes:**
- `"pf"` → `pp.runpp` (Newton-Raphson AC PF)
- `"opf"` → `pp.rundcopp` (DC OPF, linear)
- `"acopf"` → `pp.runopp` (AC OPF via PYPOWER interior-point)

`gen_costs` dict (name → $/MWh) is injected as `pp.create_poly_cost` on a deep copy of the network, so the caller's net is never modified. For `acopf`, `obj_val` is computed as `sum(cost[g] * p_mw[g])`.

### `branch_tightness(circuit, socp_result)` — per-branch SOC gap

Returns `τ_ij = |W_ij|² / (W_ii · W_jj)` for each branch, where `τ ∈ [0, 1]`:
- `τ = 1` → SOC constraint active; 2×2 minor of W has rank ≤ 1 locally
- `τ < 1` → relaxation is slack on this branch

**τ = 1 everywhere is necessary but NOT sufficient on meshed networks.** The SOC only constrains magnitudes |W_ij|, not phases arg(W_ij). Use `loop_residuals` to check phase consistency.

Returns gracefully (NaN arrays) when SOCP did not converge.

### `loop_residuals(circuit, socp_result)` — phase consistency across cycles

BFS spanning tree from the slack bus. For each non-tree branch k (i→j):
```
direct    = arctan2(Wi[k], Wr[k])     # θ_i − θ_j from this branch's W_ij
predicted = angles[i] − angles[j]     # θ_i − θ_j accumulated along the BFS tree path
residual  = wrap_to_pi(direct − predicted)
```
Nonzero residual = the W matrix satisfies every 2×2 SOC condition but is not globally rank-1. On a radial network there are no loops, so `branch_tightness` alone is sufficient.

Returns gracefully (empty arrays) when SOCP did not converge.

---

## Comparison driver (`demo_project.py`)

### `compare_solvers(circuit_factory, pandapower_factory, gen_limits, gen_costs, ...)`

Grid-agnostic. Pass two zero-argument factory callables (one Circuit, one pandapower net). Writes a four-section CSV:

1. **Summary** — solver, mode, converged, solve_time_s, obj_val
2. **Bus voltages** — side-by-side v_mag and v_ang_deg for all solvers
3. **Branch flows** — from-end P and Q (pu) for all solvers
4. **SOCP tightness** — per-branch τ, gap (1−τ), in_loop flag, loop_residual_deg

Key parameters:
- `socp_mode`: `"pf"` (default) or `"opf"` — sets SOCP objective and column label
- `include_pp_acopf`: adds `pp.runopp` as a 5th column
- `v_min`, `v_max`: voltage bounds for SOCP (pu); set loosely on cases with large impedances

Branch alignment across solvers uses **name matching** (`_align_by_name`) so insertion order differences between Circuit (lines first, then transformers) and pandapower don't cause misalignment.

### `print_summary(results, grid_label)`

Reads `results["_labels_modes"]` (dynamic, set by `compare_solvers`) and `results["_socp_tightness"]`. Prints a text table plus the SOCP diagnostics block. Handles SOCP non-convergence gracefully.

---

### `multi_start_comparison(circuit_factory, pandapower_factory, gen_limits, gen_costs, ...)`

Runs pandapower NR from `n_starts` random high-V / high-angle starting points to reveal multiple local AC solutions. SOCP and DC OPF are run **once** (convex — their result is independent of the starting point).

**Starting points:** voltage magnitudes drawn uniformly from `v_range` (default `[1.0, 1.5]` pu), angles from `angle_range` (default `[-60°, 60°]`), independently per bus. Slack bus angle is overridden to 0° by pandapower.

**NR initialization:** injects the random (V, θ) into `net.res_bus` then calls `pp.runpp(init="results")`.

**Clustering:** greedy max-norm over voltage magnitude vectors with tolerance `tol_v_cluster=0.02` pu. Two solutions are "the same" if every bus voltage differs by less than 20 mV.

**Returns dict with keys:**
```
socp, dc_opf      — convex solver results
nr_runs           — list of n_starts result dicts
nr_cluster_ids    — list[int | None]
nr_clusters       — representative result per distinct solution
nr_obj_vals       — list[float | None], gen cost ($/h) per run
starts            — list of (v_init_arr, ang_init_arr_deg)
n_converged, n_clusters
```

**Per-grid wrappers:** `multi_start_case14(n_starts, seed)` / `multi_start_wb5(n_starts, seed)`

**`print_multi_start_summary(results, grid_label)`** prints per-run table, distinct-solution cluster summary, and convex-solver reference row.

---

### Multi-start results (seed=42, 20 starts, v∈[1.0,1.5] pu, θ∈[−60°,60°])

#### IEEE 14-bus

- **1/20 starts converge.** NR has a small basin of attraction; high-V/high-angle starts mostly diverge.
- The one converged run finds a **voltage-collapse solution** (Bus07 ≈ 0 pu, Bus09 = 0.25 pu, cost = 8752 $/h) — a mathematically valid but physically unrealizable second solution to the AC PF equations.
- SOCP finds the physical high-voltage solution (cost = 5847 $/h) regardless.

#### WB5

- **8/20 starts converge** to **2 distinct local AC solutions:**

  | Cluster | Runs | min\|V\| | cost ($/h) |
  |---------|------|----------|------------|
  | 0 | 5 | 0.897 pu | **1656** |
  | 1 | 3 | 0.872 pu | **1833** |

- Both are well above the SOCP lower bound of **740 $/h** (55–59% duality gap).
- DC OPF lower bound: **325 $/h**.

---

## Visualization (`plots.py`)

All functions take pre-computed result dicts — no solvers are re-run. Each saves a PNG and returns the matplotlib `Figure`. Call `plot_all(...)` to generate everything at once.

```python
from plots import plot_all
plot_all(
    compare_results={"wb5": rwb5, "c22loop": rc22, "c22loop_asym": rc22a},
    multistart_results={"wb5": mswb5, "c22loop_asym": msc22a},
)
```

`main()` in `demo_project.py` calls this automatically after all solver runs.

### Figures produced

| Function | Output file | What it shows |
|----------|-------------|---------------|
| `plot_objective_comparison` | `fig_objectives.png` | Grouped bar chart of SOCP / DC OPF / AC OPF costs for WB5, c22loop, c22loop_asym. Duality gap % annotated on the SOCP bar when gap > 0.5%. |
| `plot_multi_start_costs` | `fig_multistart_costs.png` | Strip/dot plot — one dot per NR run, colored by cluster (grey × = diverged). Horizontal dashed reference lines for SOCP lower bound and AC OPF optimum. The primary "multiple local minima" figure. |
| `plot_voltage_profiles` | `fig_voltages.png` | Grouped bar chart of per-bus \|V\| for each distinct NR cluster vs. SOCP reference. Shows exactly where local solutions differ in voltage space. |
| `plot_socp_tightness` | `fig_tightness.png` | Horizontal bar chart of per-branch τ for WB5 and c22loop side-by-side. Both have τ≈1 everywhere; loop residuals (annotated in degrees) reveal why only WB5 has a duality gap. |
| `plot_ring_flows` | `fig_ring_flows.png` | Circular ring diagram for case22loop_asym — balanced vs. optimal dispatch shown side-by-side. Line width ∝ \|P\|, node color = cheap arc (blue, buses 1–11) / expensive arc (orange, buses 13–21). |

### Data flow

`compare_solvers` stores per-branch tightness in `results["_socp_tightness"]`:
```
branch_names        : list[str]
tau                 : ndarray (L,)
loop_residuals_deg  : dict {branch_name: residual_deg}  — non-tree branches only
max_gap, worst_branch, max_loop_residual_deg            — summary scalars
```
`plot_socp_tightness` reads directly from this key; no circuit object is needed in `plots.py`.

---

## Cases

### IEEE 14-bus (`compare_case14`)

Standard MATPOWER case14. 14 buses, 17 lines, 3 ideal transformers, 5 generators.

- **socp_mode**: `"pf"` (compare to pandapower NR as ground truth)
- **Voltage bounds**: 0.5 / 1.5 (default loose — case14 generators have reactive headroom)
- **Generator Q-limits** are **wider than canonical MATPOWER** to compensate for the omitted Bus9 shunt capacitor (19 MVAr). The Circuit model does not support bus shunts; without it, the canonical limits make SOCP infeasible.
- **SOCP tightness on case14**: τ ≈ 1 everywhere (max gap ≈ 5e-6), loop residuals up to 4.3°. Shows that τ ≈ 1 does NOT imply exactness on a meshed network.
- **DC angle discrepancy vs. pandapower**: our `b_ij = x/(r²+x²)`, pandapower uses `1/x`. On lines with r/x ≈ 0.5, angles differ by ~1°. Both are valid DC approximations.

### WB5 — Bukhsh et al. 2013 (`compare_wb5`)

5-bus meshed network designed to demonstrate that the SOCP relaxation has a non-zero **duality gap**. GenSlack at Bus1 costs $4/MWh; GenPV at Bus5 costs $1/MWh. The cheap generator is only reachable via two high-impedance lines (L02-04, L03-05: r=0.55, x=0.90 pu), creating a non-convex bottleneck.

- **socp_mode**: `"opf"` (SOCP and pp.runopp both optimise cost)
- **include_pp_acopf**: `True` (pp.runopp as 5th column = AC OPF ground truth)
- **Voltage bounds**: 0.5 / 1.5 for both SOCP and pandapower — the natural AC operating point has PQ bus voltages below 0.95, making the canonical [0.95, 1.05] limits infeasible for both SOCP and `pp.runopp`.

**Results (loose bounds):**

| Solver | obj ($/h) | Notes |
|--------|-----------|-------|
| socp_opf | **740** | Lower bound — pushes Bus05 to 1.5 pu upper bound |
| dc_opf | **325** | Another lower bound (all cheap GenPV, no voltage model) |
| pp_acopf | **1256** | True AC OPF local minimum |
| Duality gap | **515 $/h (41%)** | SOCP is non-exact here |

SOCP tightness: τ ≈ 1 at every branch (max gap ≈ 3e-9), yet loop residuals are 1.58° (L04-05) and 0.37° (L02-03). This is the canonical illustration that τ = 1 everywhere is necessary but not sufficient for exactness on meshed networks.

---

### Case22loop — Bukhsh et al. 2013 (`compare_c22loop`)

22-bus **ring** network (Bukhsh 2013). Buses 1, 3, 5, …, 21 (odd) host generators; buses 2, 4, 6, …, 22 (even) carry loads (Pd = 204.25 MW, Qd = 43.0 MVAr each after 2.15× scaling). All 22 branches: r = 0.01 pu, x = 0.05 pu, b = 0. All 11 generators share the same linear cost ($2/MWh).

- **socp_mode**: `"opf"` — minimise cost
- **include_pp_acopf**: `True`
- **Voltage bounds**: canonical [0.95, 1.05] for both SOCP and pandapower — generators are co-located with loads around the ring, so voltages stay well-controlled

**Results:**

| Solver | obj ($/h) | Notes |
|--------|-----------|-------|
| socp_opf | **4540.54** | Lower bound |
| dc_opf | **4493.50** | DC lower bound (ignores losses) |
| pp_acopf | **4540.54** | True AC OPF — matches SOCP exactly |
| Duality gap | **≈ 0** | SOCP is **exact** for this network |

**SOCP tightness**: max(1−τ) ≈ −1e-10 (numerical zero), **loop Δ = 0.0°**. The W matrix is globally rank-1 — the SOCP solution is AC-feasible. This is the exact-SOCP counterexample to WB5: same solver, different topology, zero gap.

**Multi-start** (`angle_range=(−30°, 30°)`): 12/20 starts converge, all to one cluster at 4543.92 $/h (3.38 $/h above SOCP due to AC losses). Wide-angle starts (±180°) all diverge — the ring's per-branch angle drops (~3-5°) mean NR needs a close starting point. With uniform generator costs, only one dominant operating point is observed.

**Data helpers:**
- `BUS_DATA_C22`, `BRANCH_DATA_C22`, `GEN_DATA_C22` — ring data (generated programmatically; branches via `i % 22 + 1` wrap)
- `make_c22loop_circuit()`, `make_c22loop_pandapower(vmax_pu, vmin_pu)`, `make_c22loop_gen_limits()`, `make_c22loop_gen_costs()`

### Case22loop asymmetric costs — `compare_c22loop_asym`

Same 22-bus ring as above, but generators on buses 1, 3, 5, 7, 9, 11 cost **$1/MWh** (cheap arc) and generators on buses 13, 15, 17, 19, 21 cost **$4/MWh** (expensive arc). This breaks the rotational symmetry and creates two fundamentally different feasible operating regimes.

- **socp_mode**: `"opf"` — minimise cost
- **include_pp_acopf**: `True`
- **Voltage bounds**: canonical [0.95, 1.05]

**Results:**

| Solver | obj ($/h) | Notes |
|--------|-----------|-------|
| socp_opf | **2464** | Lower bound — uses only cheap arc generators |
| dc_opf | **2244** | DC lower bound (ignores losses) |
| pp_acopf | **2464** | True AC OPF — matches SOCP exactly |
| NR flat start | **5335** | Balanced dispatch — AC feasible but expensive |
| Duality gap | **≈ 0** | SOCP is **exact** here |

**Two distinct operating regimes:**

| | Balanced (NR flat start) | Globally optimal (SOCP / pp_acopf) |
|---|---|---|
| Gen01 dispatch | ~229 MW | ~803 MW |
| Gen11 dispatch | ~204 MW | ~829 MW |
| Gen13–21 dispatch | ~204 MW each | 0 MW (idle) |
| Total cost | **5335 $/h** | **2464 $/h** |

**Why two regimes?** The ring has one extra branch beyond its spanning tree, giving one loop degree of freedom. Power can flow clockwise or counterclockwise. The flat-start NR finds a balanced dispatch (power shared around the ring); the AC OPF concentrates load on the cheap arc (buses 1–11) and idles the expensive arc.

**SOCP tightness**: max(1−τ) ≈ 3e-12, loop Δ = 0.74°. Despite the nonzero loop residual, SOCP obj = pp.runopp obj = 2464 $/h — the relaxation is exact. The residual is near-zero and does not indicate a duality gap (contrast: WB5 has loop Δ = 1.58° **and** a 41% gap).

**Multi-start** (`n_starts=30, angle_range=(−30°, 30°)`): NR finds both regimes. The cheap-arc-dominant solution and the balanced solution are distinct clusters, illustrating that the non-convex AC OPF landscape has multiple local optima even when the SOCP relaxation is exact.

**Factory helpers:** `make_c22loop_asym_gen_costs()` — returns `{gen_name: 1.0 if bus ≤ 11 else 4.0}`.

---

## Key mathematical concepts (see `theory.md` for full derivations)

**Lifted W variables.** Replace nonlinear voltage products with $W_{ii} = |V_i|^2$, $W_{ij} = V_i V_j^*$. Power balance becomes linear in W; the only nonlinearity is the rank-1 constraint $\mathbf{W} = \mathbf{V}\mathbf{V}^H$.

**SOC relaxation.** Per-branch SOC comes from the 2×2 principal submatrix of W. Physical voltages require $\det(\mathbf{W}^{(ij)}) = 0$, i.e. $|W_{ij}|^2 = W_{ii}W_{jj}$. Relaxing equality to inequality gives the convex constraint $|W_{ij}|^2 \leq W_{ii}W_{jj}$, which is equivalent to the standard SOC form used in the code.

**Branch tightness τ.** $\tau_k = |W_{ij}|^2 / (W_{ii} W_{jj}) \in [0,1]$. $\tau_k < 1$ certifies inexactness on that branch. $\tau_k = 1$ everywhere is necessary but not sufficient for exactness on meshed networks.

**Loop residuals.** BFS from slack assigns tree angles. For each non-tree branch $k$, the residual is $\delta_k = \phi_{ij}^{\text{direct}} - \phi_{ij}^{\text{tree}}$, where $\phi_{ij}^{\text{direct}} = \arctan(W_{ij}^I / W_{ij}^R)$. Nonzero residual means phase inconsistency around that fundamental cycle — the W matrix cannot correspond to any global phasor assignment even if all $\tau_k = 1$.

**Radial exactness.** On a tree network, no non-tree branches exist, so no loop residuals exist. $\tau_k = 1$ everywhere then guarantees global rank-1, meaning the SOCP solution is AC-feasible and the relaxation is exact. This is the main practical motivation for using SOCP on distribution networks.

---

## Interactive CLI (`my_opfs.py`)

Run with `python my_opfs.py`.  Six-step terminal session; full usage in `my_opfs_guide.md`.

**Step 1 — SOCP mode** (mutually exclusive): SOCP-PF, SOCP-OPF, or skip.

**Step 2 — Additional solvers** (multi-select): DC-OPF, PP-NR, PP-DCOPF, PP-ACOPF.

**Step 3 — Grid**: IEEE 14-bus, WB5, Case22loop (uniform), Case22loop (asymmetric).

**Step 4 — Generator costs**: shows defaults; optionally accepts a comma-separated list or a CSV file (auto-detects 1-column numeric or 2-column `gen_name,cost` format).

**Step 5 — Metrics**: any subset of voltage magnitudes, voltage angles, branch P/Q flows, objective value, convergence, solve time, SOCP τ per branch, loop residuals.

**Step 6 — Save**: optional CSV path (passed to `compare_solvers`) and/or plot directory (`fig_tightness.png`, `fig_objectives.png`).

**Implementation notes:**
- All prompts run before heavy imports — the menu feels instant.
- `compare_solvers` always runs all solvers; the solver menu is a display filter only.
- SOCP τ and loop residuals print even when SOCP is skipped from display (with a note).
- WB5 uses `v_min=0.5, v_max=1.5` automatically; Case22loop variants use `[0.95, 1.05]`.
- When user declines CSV save, a temp file is used internally and deleted (because `compare_solvers` always opens `output_csv`).

---

## Bugs fixed in this session

### 1. PV bus voltage fixed in `opf` mode (critical)

**Location:** `opfs._socp_cvxpy`, lines around the PV constraint block.

**Bug:** `Wd[pv_i] == v_pv**2` was applied in **both** `pf` and `opf` modes.

**Effect:** In `opf` mode, fixing PV bus voltages to their setpoints over-constrains the AC OPF. For WB5 with `v_min=0.95, v_max=1.05`, it made the SOCP infeasible (CLARABEL and SCS both returned infeasible, then the `else` clause returned "no suitable cvxpy solver found").

**Fix:** PV equality constraints are now only added when `mode == "pf"`. In `opf` mode, PV bus voltages are free within `[v_min, v_max]` — this is the correct SOCP relaxation of AC OPF.

### 2. `branch_tightness` and `loop_residuals` raised on SOCP failure

**Bug:** Both functions raised `ValueError` when `socp_result["details"]` was missing `Wr`/`Wi` (which happens when SOCP does not converge). This crashed `compare_solvers`.

**Fix:** Both now return graceful empty/NaN results instead of raising, and `compare_solvers`/`print_summary` handle NaN tightness data with a "SOCP did not converge" message.

### 3. WB5 infeasible with canonical `[0.95, 1.05]` voltage limits

**Root cause:** The WB5 network has high-impedance lines (r=0.55, x=0.90 pu). At the natural AC operating point (pp.runpp without voltage limits), PQ buses sit at 0.90–0.94 pu — below 0.95. The AC OPF with strict voltage limits is genuinely infeasible.

**Resolution:** `compare_wb5` uses `v_min=0.5, v_max=1.5` for the SOCP, and passes `make_wb5_pandapower(vmax_pu=1.5, vmin_pu=0.5)` as the pandapower factory so `pp.runopp` also uses loose limits. The duality gap is a property of the network topology and costs, independent of the voltage bounds.

### 4. IEEE 14-bus SOCP infeasible with canonical Q-limits

**Root cause:** The Circuit model does not support bus shunt elements. Bus9 has a 19 MVAr shunt capacitor in canonical case14; without it, generators need more reactive headroom than the original Qmax values allow.

**Resolution:** Q-limits are widened in `GEN_DATA` (documented in the module docstring). This is a modelling limitation, not a solver bug.
