# AC SOCP and Linear DC OPF for the PythonPowerFlow Framework

## Overview

This project extends the PythonPowerFlow `Circuit` framework with two OPF solvers in the new module `opfs.py`. Both accept a fully-populated `Circuit` object and return bus voltages, voltage angles, and branch power flows, with an optional CSV export. Results are verified against pandapower reference solutions.

- **`solve_socp`** — convex relaxation of the AC OPF (Second-Order Cone Program)
- **`solve_dc_opf`** — linearised DC OPF (Linear Program)

---

## Mathematical Formulations

### AC SOCP Relaxation

The AC OPF is relaxed to a Second-Order Cone Program (SOCP) following Jabr (2006) and Lavaei & Low (2012). The key substitution replaces the nonlinear voltage products with lifted variables:

$$W_{ii} = |V_i|^2, \qquad W_{ij} = V_i V_j^* = W_{ij}^R + j\,W_{ij}^I$$

**Decision variables:** $W_{ii}$ (diagonal), $W_{ij}^R$, $W_{ij}^I$ (one per branch $k$), $P_g$, $Q_g$ (per generator).

**Objective (OPF mode):** $\min \displaystyle\sum_{g} c_{1,g}\, P_g$

**Constraints:**

$$V_{\min}^2 \leq W_{ii} \leq V_{\max}^2, \quad W_{\text{slack}} = V_{\text{slack}}^2, \quad W_{i} = V_{i,\text{set}}^2 \; \forall i \in \mathcal{V}_{\text{PV}}$$

$$P_g^{\min} \leq P_g \leq P_g^{\max}, \qquad Q_g^{\min} \leq Q_g \leq Q_g^{\max}$$

$$\sum_{j} \bigl(G_{ij} W_{ij}^R + B_{ij} W_{ij}^I\bigr) = \sum_{g \in i} P_g - P_{\text{load},i}, \quad \sum_{j} \bigl(G_{ij} W_{ij}^I - B_{ij} W_{ij}^R\bigr) = \sum_{g \in i} Q_g - Q_{\text{load},i}$$

$$\left\| \begin{pmatrix} 2W_{ij}^R \\ 2W_{ij}^I \\ W_{ii} - W_{jj} \end{pmatrix} \right\|_2 \leq W_{ii} + W_{jj} \quad \forall k = (i,j)$$

The SOC constraint per branch replaces the rank-1 condition $\mathrm{rank}(W)=1$. Voltage angles are recovered by BFS from the slack bus using $\angle V_i V_j^* = \arctan(W_{ij}^I / W_{ij}^R)$.

### Linear DC OPF

The DC OPF assumes $|V_i| \equiv 1\,\text{pu}$ and linearises around small angle differences, reducing to an LP.

**Decision variables:** $\theta_i$ (bus angles, rad), $P_g$ (generator dispatch, pu).

**Objective (OPF mode):** $\min \displaystyle\sum_{g} c_{1,g}\, P_g$

**Constraints:**

$$\mathbf{B}_{\text{DC}}\,\mathbf{\Theta} = \mathbf{A}_{\text{gen}}\,\mathbf{P}_g - \mathbf{P}_{\text{load}}, \qquad \theta_{\text{slack}} = 0, \qquad P_g^{\min} \leq P_g \leq P_g^{\max}$$

where $[\mathbf{B}_{\text{DC}}]_{ij} = -x_{ij}/(r_{ij}^2+x_{ij}^2)$ for $i \neq j$ (matching pandapower's susceptance convention). Branch flows are lossless: $P_{ij} = b_{ij}(\theta_i - \theta_j)$, $P_{to} = -P_{fr}$, $Q \equiv 0$.

---

## API — Inputs and Outputs

Both functions share the same output schema.

```python
solve_socp(
    circuit,           # Circuit — populated with buses, lines, generators, loads
    mode    = "pf",    # "pf": fix PV dispatch, slack free | "opf": minimise cost
    verbose = False,   # pass solver verbosity flag to cvxpy
    output_csv = None, # path or None — writes bus voltages and line flows
    gen_limits = None, # dict  gen_name → {"p_min","p_max","q_min","q_max"} (MW/MVAr)
    gen_costs  = None, # dict  gen_name → cost_c1 ($/MWh)
    v_min = 0.5,       # lower voltage bound (pu)
    v_max = 1.5,       # upper voltage bound (pu)
) -> dict

solve_dc_opf(
    circuit,           # Circuit — same as above
    mode    = "opf",   # "opf": minimise cost | "pf": fix PV dispatch, slack free
    verbose = False,
    output_csv = None,
    gen_limits = None, # dict  gen_name → {"p_min","p_max"} (MW)
    gen_costs  = None, # dict  gen_name → cost_c1 ($/MWh)
) -> dict
```

| Output key | Type | Description |
|---|---|---|
| `source` | `str` | `"socp"` or `"dc_opf"` |
| `v_mag` | `ndarray (N,)` | Bus voltage magnitudes (pu); DC returns all ones |
| `v_ang_deg` | `ndarray (N,)` | Bus voltage angles (degrees), slack = 0 |
| `p_fr`, `q_fr` | `ndarray (L,)` | Real/reactive power at the from-end of each branch (pu) |
| `p_to`, `q_to` | `ndarray (L,)` | Real/reactive power at the to-end; DC: `p_to = −p_fr`, `q = 0` |
| `converged` | `bool` | `True` if solver reached optimal or near-optimal |
| `details` | `dict` | `obj_val`, `backend_used`, `solve_time_s`, `p_gen_pu`, `q_gen_pu` |

---

## Solvers

Both functions use **cvxpy** as the modelling layer. Solvers are attempted in priority order:

| Solver | Type | Notes                                               |
|---|---|-----------------------------------------------------|
| **CLARABEL** | Interior-point (conic) | Default; shipped with cvxpy; handles both SOCP and LP |
| **HIGHS** | Simplex / IPM (LP) | DC OPF only; efficient open-source LP solver        |
| **GUROBI** | Commercial | Used if a licence is available                      |
| **SCS** | First-order splitting | Slowest; always available as a fallback             |

---

## Verification

Both solvers are tested in `test_opfs.py` against **pandapower 3.4.0** on a 3-bus, 345 kV, 100 MVA test network (transmission lines only, no transformers):

| Test | Method | Reference | Tolerance |
|---|---|---|---|
| Voltage magnitudes | SOCP `pf` | `pp.runpp` (Newton-Raphson) | 5 × 10⁻³ pu |
| Voltage angles | SOCP `pf` | `pp.runpp` | 0.5° |
| Branch real power | SOCP `pf` | `pp.runpp` | 5 × 10⁻³ pu |
| Generator dispatch | DC OPF | `pp.rundcopp` | 1 MW |
| Voltage angles | DC OPF | `pp.rundcopp` | 0.1° |
| Branch real power | DC OPF | `pp.rundcopp` | 5 × 10⁻³ pu |