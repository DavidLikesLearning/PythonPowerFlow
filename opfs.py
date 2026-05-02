"""
AC SOCP relaxation, linear DC OPF, and pandapower wrapper for PythonPowerFlow Circuit objects.

SOCP variables:  Wd[i] = |V_i|²,  Wr[k]/Wi[k] = Re/Im(V_i·V_j*)
SOC per branch k:  ‖[2Wr, 2Wi, Wd_i−Wd_j]‖₂ ≤ Wd_i+Wd_j

DC OPF variables:  θ[i] (bus angles, rad),  Pg[g] (generator dispatch, pu)
DC power balance:  B_DC · θ = A_gen · Pg − P_load   (lossless, V≡1 pu)

Objective (opf mode):  min  Σ_g cost_g · Pg
         (pf mode):    fix PV generators' Pg, slack free, feasibility

All three solvers return the same dict with keys:
    source, v_mag, v_ang_deg, p_fr, q_fr, p_to, q_to, converged, details

Public API:
    solve_socp(circuit, mode, verbose, output_csv, gen_limits, gen_costs, v_min, v_max)
    solve_dc_opf(circuit, mode, verbose, output_csv, gen_limits, gen_costs)
    solve_pandapower(net, mode, verbose, output_csv, gen_costs, sn_mva)
"""
from __future__ import annotations

import copy
import csv
import time
from collections import deque

import numpy as np
import cvxpy as cp

try:
    import pandapower as pp
    _PP_AVAILABLE = True
except ImportError:
    _PP_AVAILABLE = False

from bus import BusType
from settings import grid_settings


# ── Data extraction ────────────────────────────────────────────────────────

def _extract_from_circuit(circuit, gen_limits, gen_costs,
                          v_min, v_max) -> dict:
    sbase = grid_settings.sbase

    ybus_df = circuit.calc_ybus()
    bus_names = list(ybus_df.index)
    bus_idx = {name: i for i, name in enumerate(bus_names)}
    N = len(bus_names)
    Y = ybus_df.to_numpy()
    G, B = Y.real, Y.imag

    slack_idx = next(
        bus_idx[name]
        for name, bus in circuit.buses.items()
        if bus.bus_type == BusType.Slack
    )
    v_slack = circuit.buses[bus_names[slack_idx]].vpu

    # PV buses (excluding slack): voltage magnitude is fixed
    pv_constraints = []  # list of (bus_idx, v_pu)
    for name, bus in circuit.buses.items():
        if bus.bus_type == BusType.PV:
            pv_constraints.append((bus_idx[name], bus.vpu))

    bp, branch_names = [], []
    for ln in circuit.transmission_lines.values():
        r, x, b_sh = ln.r, ln.x, ln.b
        d = r**2 + x**2
        bp.append(dict(i=bus_idx[ln.bus1_name], j=bus_idx[ln.bus2_name],
                       g=r/d, b=-x/d, b_sh=b_sh))
        branch_names.append(ln.name)
    for tx in circuit.transformers.values():
        r, x = tx.r, tx.x
        d = r**2 + x**2
        bp.append(dict(i=bus_idx[tx.bus1_name], j=bus_idx[tx.bus2_name],
                       g=r/d, b=-x/d, b_sh=0.0))
        branch_names.append(tx.name)
    L = len(bp)

    P_load, Q_load = np.zeros(N), np.zeros(N)
    for ld in circuit.loads.values():
        i = bus_idx[ld.bus_name]
        P_load[i] += ld.mw / sbase
        Q_load[i] += ld.mvar / sbase

    gen_list = list(circuit.generators.values())
    ng = len(gen_list)
    gen_bus_idx = [bus_idx[g.bus_name] for g in gen_list]

    # Mark which generators are at the slack bus
    slack_gen_mask = [bus_idx[g.bus_name] == slack_idx for g in gen_list]

    gl = gen_limits or {}
    gc = gen_costs or {}
    P_min = np.array([gl.get(g.name, {}).get("p_min", 0.0) / sbase for g in gen_list])
    P_max = np.array([gl.get(g.name, {}).get("p_max", 1e4) / sbase for g in gen_list])
    Q_min = np.array([gl.get(g.name, {}).get("q_min", -1e4) / sbase for g in gen_list])
    Q_max = np.array([gl.get(g.name, {}).get("q_max",  1e4) / sbase for g in gen_list])
    cost  = np.array([gc.get(g.name, 0.0) * sbase for g in gen_list])

    return dict(
        N=N, L=L, G=G, B=B,
        bp=bp, branch_names=branch_names, bus_names=bus_names,
        slack_idx=slack_idx, v_slack=v_slack,
        pv_constraints=pv_constraints,
        v_min=v_min, v_max=v_max,
        P_load=P_load, Q_load=Q_load,
        gen_bus_idx=gen_bus_idx, ng=ng, gen_list=gen_list,
        slack_gen_mask=slack_gen_mask,
        P_min=P_min, P_max=P_max, Q_min=Q_min, Q_max=Q_max,
        cost=cost,
    )


# ── Angle recovery (BFS from slack) ───────────────────────────────────────

def _recover_angles(Wd, Wr, Wi, bp, slack_idx, N) -> np.ndarray:
    adj = {b: [] for b in range(N)}
    for k, b in enumerate(bp):
        adj[b["i"]].append((b["j"], k, True))
        adj[b["j"]].append((b["i"], k, False))
    angles = np.zeros(N)
    visited, queue = {slack_idx}, deque([slack_idx])
    while queue:
        n = queue.popleft()
        for nbr, k, fwd in adj[n]:
            if nbr in visited:
                continue
            visited.add(nbr)
            queue.append(nbr)
            angles[nbr] = (angles[n] - np.arctan2(Wi[k], Wr[k])
                           if fwd else angles[n] + np.arctan2(Wi[k], Wr[k]))
    return angles


# ── Line-flow recovery ─────────────────────────────────────────────────────

def _compute_line_flows(Wd, Wr, Wi, bp):
    L = len(bp)
    p_fr, q_fr, p_to, q_to = (np.zeros(L) for _ in range(4))
    for k, br in enumerate(bp):
        i, j = br["i"], br["j"]
        g, b_s, b_sh = br["g"], br["b"], br["b_sh"]
        Wii, Wjj = Wd[i], Wd[j]
        p_fr[k] = g*Wii - g*Wr[k] - b_s*Wi[k]
        q_fr[k] = -(b_s + b_sh/2)*Wii + b_s*Wr[k] - g*Wi[k]
        p_to[k] = g*Wjj - g*Wr[k] + b_s*Wi[k]
        q_to[k] = -(b_s + b_sh/2)*Wjj + b_s*Wr[k] + g*Wi[k]
    return p_fr, q_fr, p_to, q_to


# ── SOCP via cvxpy ────────────────────────────────────────────────────────

def _socp_cvxpy(d, mode, verbose):
    N, L, ng = d["N"], d["L"], d["ng"]
    G, B, bp = d["G"], d["B"], d["bp"]

    Wd = cp.Variable(N, nonneg=True)
    Wr = cp.Variable(L)
    Wi = cp.Variable(L)
    Pg = cp.Variable(ng, nonneg=True)
    Qg = cp.Variable(ng)

    cons = [
        Wd >= d["v_min"]**2, Wd <= d["v_max"]**2,
        Wd[d["slack_idx"]] == d["v_slack"]**2,
        Pg >= d["P_min"], Pg <= d["P_max"],
        Qg >= d["Q_min"], Qg <= d["Q_max"],
    ]

    # PV bus voltage equality — pf mode only.
    # In opf mode, PV-bus voltages are free within [v_min, v_max]; fixing them
    # to the setpoint over-constrains the AC OPF and can cause infeasibility.
    if mode == "pf":
        for pv_i, v_pv in d["pv_constraints"]:
            cons.append(Wd[pv_i] == v_pv**2)

    for k, br in enumerate(bp):
        cons.append(
            cp.norm(cp.vstack([2*Wr[k], 2*Wi[k], Wd[br["i"]]-Wd[br["j"]]]), 2)
            <= Wd[br["i"]] + Wd[br["j"]]
        )

    for i in range(N):
        p_inj = G[i, i] * Wd[i]
        q_inj = -B[i, i] * Wd[i]
        for k, br in enumerate(bp):
            ii, jj = br["i"], br["j"]
            if ii == i:
                p_inj = p_inj + G[i, jj]*Wr[k] + B[i, jj]*Wi[k]
                q_inj = q_inj - B[i, jj]*Wr[k] + G[i, jj]*Wi[k]
            elif jj == i:
                p_inj = p_inj + G[i, ii]*Wr[k] - B[i, ii]*Wi[k]
                q_inj = q_inj - B[i, ii]*Wr[k] - G[i, ii]*Wi[k]
        at = [g for g, gb in enumerate(d["gen_bus_idx"]) if gb == i]
        pg_i = cp.sum([Pg[g] for g in at]) if at else 0
        qg_i = cp.sum([Qg[g] for g in at]) if at else 0
        cons += [p_inj == pg_i - d["P_load"][i],
                 q_inj == qg_i - d["Q_load"][i]]

    # In pf mode, fix Pg for non-slack generators only.
    # Also add a tiny cost on the slack generator so the solver selects the
    # unique minimum-generation point that matches the Newton-Raphson solution
    # (without this, the relaxed feasible set admits many solutions).
    if mode == "pf":
        sbase = grid_settings.sbase
        for g, gen in enumerate(d["gen_list"]):
            if not d["slack_gen_mask"][g]:
                cons.append(Pg[g] == gen.mw_setpoint / sbase)
        pf_cost = np.where(d["slack_gen_mask"], 1.0, 0.0)
        objective = cp.Minimize(d["cost"] @ Pg + pf_cost @ Pg)
    else:
        objective = cp.Minimize(d["cost"] @ Pg)

    prob = cp.Problem(objective, cons)
    t0 = time.perf_counter()
    for solver_name in ["CLARABEL", "GUROBI", "SCS"]:
        if solver_name not in cp.installed_solvers():
            continue
        try:
            prob.solve(solver=getattr(cp, solver_name), verbose=verbose)
            if prob.status not in (None, "infeasible", "infeasible_inaccurate"):
                break
        except Exception:
            continue
    else:
        return None, "no suitable cvxpy solver found"
    elapsed = time.perf_counter() - t0

    if prob.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
        return None, f"solver status={prob.status}"

    Wd_v, Wr_v, Wi_v = Wd.value, Wr.value, Wi.value
    angles = _recover_angles(Wd_v, Wr_v, Wi_v, bp, d["slack_idx"], N)
    p_fr, q_fr, p_to, q_to = _compute_line_flows(Wd_v, Wr_v, Wi_v, bp)

    return {
        "source": "socp",
        "v_mag": np.sqrt(np.maximum(Wd_v, 0.0)),
        "v_ang_deg": np.degrees(angles),
        "p_fr": p_fr, "q_fr": q_fr, "p_to": p_to, "q_to": q_to,
        "converged": True,
        "details": dict(
            obj_val=float(prob.objective.value),
            backend_used="cvxpy", solve_time_s=elapsed,
            p_gen_pu=Pg.value.tolist(), q_gen_pu=Qg.value.tolist(),
            # Lifted W variables — surfaced for relaxation-gap analysis.
            # Order matches the bp list (lines first, then transformers).
            Wd=Wd_v.tolist(), Wr=Wr_v.tolist(), Wi=Wi_v.tolist(),
        ),
    }, None


# ── DC susceptance matrix ─────────────────────────────────────────────────

def _build_dc_B(d) -> np.ndarray:
    """DC bus susceptance matrix B s.t. B·θ = P_inj.
    Uses b_ij = x_ij/(r_ij²+x_ij²) = Im(y_series), matching pandapower's DC model.
    Shunt susceptances are ignored (standard DC approximation).
    """
    N = d["N"]
    B = np.zeros((N, N))
    for br in d["bp"]:
        i, j = br["i"], br["j"]
        b_ij = -br["b"]          # x/(r²+x²) — positive series susceptance
        B[i, i] += b_ij
        B[j, j] += b_ij
        B[i, j] -= b_ij
        B[j, i] -= b_ij
    return B


def _dc_line_flows(theta, bp) -> np.ndarray:
    """P_from[k] = b_ij · (θ_i − θ_j) for each branch k (lossless DC)."""
    p_fr = np.zeros(len(bp))
    for k, br in enumerate(bp):
        b_ij = -br["b"]
        p_fr[k] = b_ij * (theta[br["i"]] - theta[br["j"]])
    return p_fr


# ── DC OPF via cvxpy LP ───────────────────────────────────────────────────

def _dc_lp_cvxpy(d, mode, verbose):
    N, L, ng = d["N"], d["L"], d["ng"]
    B_DC = _build_dc_B(d)

    # generator-to-bus incidence matrix
    A_gen = np.zeros((N, ng))
    for g, gi in enumerate(d["gen_bus_idx"]):
        A_gen[gi, g] = 1.0

    theta = cp.Variable(N)
    Pg    = cp.Variable(ng, nonneg=True)

    cons = [
        theta[d["slack_idx"]] == 0.0,
        Pg >= d["P_min"], Pg <= d["P_max"],
        B_DC @ theta == A_gen @ Pg - d["P_load"],
    ]

    if mode == "pf":
        sbase = grid_settings.sbase
        for g, gen in enumerate(d["gen_list"]):
            if not d["slack_gen_mask"][g]:
                cons.append(Pg[g] == gen.mw_setpoint / sbase)

    prob = cp.Problem(cp.Minimize(d["cost"] @ Pg), cons)
    t0 = time.perf_counter()
    for solver_name in ["CLARABEL", "HIGHS", "GUROBI", "SCS"]:
        if solver_name not in cp.installed_solvers():
            continue
        try:
            prob.solve(solver=getattr(cp, solver_name), verbose=verbose)
            if prob.status not in (None, "infeasible", "infeasible_inaccurate"):
                break
        except Exception:
            continue
    else:
        return None, "no suitable cvxpy solver found"
    elapsed = time.perf_counter() - t0

    if prob.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
        return None, f"solver status={prob.status}"

    theta_v = theta.value
    Pg_v    = Pg.value
    p_fr    = _dc_line_flows(theta_v, d["bp"])

    return {
        "source":     "dc_opf",
        "v_mag":      np.ones(N),
        "v_ang_deg":  np.degrees(theta_v),
        "p_fr": p_fr,          "q_fr": np.zeros(L),
        "p_to": -p_fr,         "q_to": np.zeros(L),
        "converged": True,
        "details": dict(
            obj_val=float(prob.objective.value),
            backend_used="cvxpy", solve_time_s=elapsed,
            p_gen_pu=Pg_v.tolist(), q_gen_pu=[0.0] * ng,
        ),
    }, None


# ── CSV output ─────────────────────────────────────────────────────────────

def _write_results_csv(result, bus_names, branch_names, path):
    """Write bus voltages/angles and branch flows to a two-section CSV file."""
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["bus_name", "v_mag_pu", "v_ang_deg"])
        for name, vm, va in zip(bus_names, result["v_mag"], result["v_ang_deg"]):
            w.writerow([name, f"{vm:.6f}", f"{va:.6f}"])
        w.writerow([])
        w.writerow(["branch_name", "p_from_pu", "q_from_pu", "p_to_pu", "q_to_pu"])
        for name, pf, qf, pt, qt in zip(
            branch_names, result["p_fr"], result["q_fr"],
            result["p_to"], result["q_to"]
        ):
            w.writerow([name, f"{pf:.6f}", f"{qf:.6f}", f"{pt:.6f}", f"{qt:.6f}"])


# ── Public API ─────────────────────────────────────────────────────────────

def solve_socp(circuit, mode="pf", verbose=False,
               output_csv=None, gen_limits=None, gen_costs=None,
               v_min=0.5, v_max=1.5) -> dict:
    """
    Solve SOCP relaxation of AC OPF for a PythonPowerFlow Circuit.

    Parameters
    ----------
    circuit     : Circuit object (populated with buses, lines, generators, loads)
    mode        : "pf" (fix PV dispatch, slack free) or "opf" (minimise cost)
    verbose     : passed to cvxpy solver
    output_csv  : file path or None; if given, writes bus voltages and line flows
    gen_limits  : dict  gen_name -> {"p_min", "p_max", "q_min", "q_max"}  (MW/MVAr)
    gen_costs   : dict  gen_name -> cost_c1  ($/MWh, scaled to sbase internally)
    v_min       : lower voltage bound in pu (default 0.5)
    v_max       : upper voltage bound in pu (default 1.5)

    Returns
    -------
    dict with keys:
        source, v_mag, v_ang_deg, p_fr, q_fr, p_to, q_to, converged, details
    """
    d = _extract_from_circuit(circuit, gen_limits, gen_costs, v_min, v_max)
    result, err = _socp_cvxpy(d, mode, verbose)

    if result is None:
        N, L = d["N"], d["L"]
        return {
            "source": "socp",
            "v_mag": np.ones(N), "v_ang_deg": np.zeros(N),
            "p_fr": np.zeros(L), "q_fr": np.zeros(L),
            "p_to": np.zeros(L), "q_to": np.zeros(L),
            "converged": False,
            "details": dict(message=err),
        }

    if output_csv:
        _write_results_csv(result, d["bus_names"], d["branch_names"], output_csv)
    return result


def solve_dc_opf(circuit, mode="opf", verbose=False,
                 output_csv=None, gen_limits=None, gen_costs=None) -> dict:
    """
    Solve linear DC OPF (LP) for a PythonPowerFlow Circuit.

    Assumes V ≡ 1 pu everywhere (DC approximation). Reactive power is not
    modelled; q_fr and q_to are returned as zero arrays.

    Parameters
    ----------
    circuit     : Circuit object (populated with buses, lines, generators, loads)
    mode        : "opf" (minimise cost) or "pf" (fix PV dispatch, slack free)
    verbose     : passed to cvxpy solver
    output_csv  : file path or None; if given, writes bus angles and line flows
    gen_limits  : dict  gen_name -> {"p_min", "p_max"}  (MW)
    gen_costs   : dict  gen_name -> cost_c1  ($/MWh, scaled to sbase internally)

    Returns
    -------
    dict with keys:
        source, v_mag (ones), v_ang_deg, p_fr, q_fr (zeros), p_to, q_to (zeros),
        converged, details
    """
    d = _extract_from_circuit(circuit, gen_limits, gen_costs, v_min=0.5, v_max=1.5)
    result, err = _dc_lp_cvxpy(d, mode, verbose)

    if result is None:
        N, L = d["N"], d["L"]
        return {
            "source": "dc_opf",
            "v_mag": np.ones(N), "v_ang_deg": np.zeros(N),
            "p_fr": np.zeros(L), "q_fr": np.zeros(L),
            "p_to": np.zeros(L), "q_to": np.zeros(L),
            "converged": False,
            "details": dict(message=err),
        }

    if output_csv:
        _write_results_csv(result, d["bus_names"], d["branch_names"], output_csv)
    return result


def solve_pandapower(net, mode="pf", verbose=False,
                     output_csv=None, gen_costs=None, sn_mva=None) -> dict:
    """
    Run pandapower AC power flow or DC OPF and return results in the standard format.

    Results are directly comparable to solve_socp() and solve_dc_opf() output:
    all power flows are in per-unit on the network's MVA base.

    Parameters
    ----------
    net         : pandapower network (pre-built with buses, lines, loads, generators)
    mode        : "pf"     — AC Newton-Raphson via pp.runpp
                  "opf"   — DC OPF via pp.rundcopp (linear, lossless)
                  "acopf" — AC OPF via pp.runopp (nonlinear; requires PYPOWER)
    verbose     : passed to the pandapower solver
    output_csv  : file path or None; if given, writes bus voltages/angles and line
                  flows in the same two-section format as the other solvers
    gen_costs   : dict  element_name -> cost ($/MWh); adds linear poly costs to
                  matching ext_grid and gen elements (applied to a copy of net,
                  so the original is not modified)
    sn_mva      : MVA base for per-unit conversion (default: net.sn_mva)

    Returns
    -------
    dict with keys:
        source       : "pandapower"
        v_mag        : np.ndarray of voltage magnitudes in pu (one per bus)
        v_ang_deg    : np.ndarray of voltage angles in degrees (one per bus)
        p_fr         : np.ndarray of from-end real power in pu (one per line)
        q_fr         : np.ndarray of from-end reactive power in pu (zero for DC)
        p_to         : np.ndarray of to-end real power in pu
        q_to         : np.ndarray of to-end reactive power in pu (zero for DC)
        converged    : bool
        details      : dict with solve_time_s, backend_used, and (for opf mode)
                       p_gen_mw and p_ext_grid_mw dispatch arrays
    """
    if not _PP_AVAILABLE:
        raise ImportError("pandapower is not installed")

    sn_mva = float(sn_mva or net.sn_mva)

    # Work on a copy when we need to inject costs, so the caller's net is untouched
    if gen_costs and mode in ("opf", "acopf"):
        net = copy.deepcopy(net)
        for idx, row in net.ext_grid.iterrows():
            name = row.get("name", f"ext_grid_{idx}")
            if name in gen_costs:
                pp.create_poly_cost(net, idx, "ext_grid",
                                    cp1_eur_per_mw=gen_costs[name])
        for idx, row in net.gen.iterrows():
            name = row.get("name", f"gen_{idx}")
            if name in gen_costs:
                pp.create_poly_cost(net, idx, "gen",
                                    cp1_eur_per_mw=gen_costs[name])

    t0 = time.perf_counter()
    try:
        if mode == "pf":
            pp.runpp(net, algorithm="nr", calculate_voltage_angles=True,
                     max_iteration=50, verbose=verbose)
            converged = bool(net["converged"])
        elif mode == "opf":
            pp.rundcopp(net, verbose=verbose)
            converged = bool(net["OPF_converged"])
        elif mode == "acopf":
            pp.runopp(net, verbose=verbose)
            converged = bool(net["OPF_converged"])
        else:
            raise ValueError(f"mode must be 'pf', 'opf', or 'acopf', got {mode!r}")
    except Exception as e:
        N = len(net.bus)
        L = len(net.line)
        return {
            "source": "pandapower",
            "v_mag": np.ones(N), "v_ang_deg": np.zeros(N),
            "p_fr": np.zeros(L), "q_fr": np.zeros(L),
            "p_to": np.zeros(L), "q_to": np.zeros(L),
            "converged": False,
            "details": dict(message=str(e), backend_used="pandapower"),
        }
    elapsed = time.perf_counter() - t0

    bus_names   = net.bus["name"].tolist()
    branch_names = net.line["name"].tolist()

    v_mag = net.res_bus["vm_pu"].values.copy()
    v_ang = net.res_bus["va_degree"].values.copy()
    p_fr  = net.res_line["p_from_mw"].values.copy()  / sn_mva
    q_fr  = net.res_line["q_from_mvar"].values.copy() / sn_mva
    p_to  = net.res_line["p_to_mw"].values.copy()    / sn_mva
    q_to  = net.res_line["q_to_mvar"].values.copy()  / sn_mva

    details = dict(
        mode=mode,
        solve_time_s=elapsed,
        backend_used="pandapower",
        p_gen_mw=net.res_gen["p_mw"].values.tolist(),
        p_ext_grid_mw=net.res_ext_grid["p_mw"].values.tolist(),
    )
    if mode == "acopf" and gen_costs:
        obj = 0.0
        for idx, row in net.ext_grid.iterrows():
            name = row.get("name", f"ext_grid_{idx}")
            if name in gen_costs:
                obj += net.res_ext_grid.loc[idx, "p_mw"] * gen_costs[name]
        for idx, row in net.gen.iterrows():
            name = row.get("name", f"gen_{idx}")
            if name in gen_costs:
                obj += net.res_gen.loc[idx, "p_mw"] * gen_costs[name]
        details["obj_val"] = obj

    result = {
        "source":    "pandapower",
        "v_mag":     v_mag,
        "v_ang_deg": v_ang,
        "p_fr": p_fr, "q_fr": q_fr,
        "p_to": p_to, "q_to": q_to,
        "converged": converged,
        "details":   details,
    }

    if output_csv:
        _write_results_csv(result, bus_names, branch_names, output_csv)

    return result


# ── SOCP relaxation-gap diagnostics ───────────────────────────────────────

def _branch_pairs_and_names(circuit):
    """Bus-index pairs and branch names in the same order as solve_socp's bp."""
    bus_names = list(circuit.calc_ybus().index)
    bus_idx = {n: i for i, n in enumerate(bus_names)}
    pairs, names = [], []
    for ln in circuit.transmission_lines.values():
        pairs.append((bus_idx[ln.bus1_name], bus_idx[ln.bus2_name]))
        names.append(ln.name)
    for tx in circuit.transformers.values():
        pairs.append((bus_idx[tx.bus1_name], bus_idx[tx.bus2_name]))
        names.append(tx.name)
    return bus_idx, pairs, names


def branch_tightness(circuit, socp_result) -> dict:
    """Per-branch SOC tightness ratio τ_ij = |W_ij|² / (W_ii · W_jj).

    For each branch, τ ∈ [0, 1]:
        τ = 1 → SOC constraint is active; the 2×2 principal minor of W
                involving (i, j) has rank ≤ 1
        τ < 1 → relaxation is slack on this branch; |W_ij| is below the
                physical bound √(W_ii · W_jj) — no real voltages can
                produce this lifted W locally

    **Necessary, not sufficient.** τ = 1 at every branch is required for
    the relaxation to be exact, but on meshed networks it is not enough:
    the SOC constraint only fixes magnitudes |W_ij|, not phases arg(W_ij),
    so the W matrix can satisfy every 2×2 condition while still failing
    global rank-1 around loops. Use loop_residuals() for that check.

    On a radial (tree) network there are no loops, and τ = 1 everywhere
    *does* imply global rank-1, so this single diagnostic is sufficient.

    Parameters
    ----------
    circuit       : same Circuit object passed to solve_socp
    socp_result   : dict returned by solve_socp (must include details.Wr, Wi)

    Returns
    -------
    dict with keys:
        branch_names  : list[str]                 (length L)
        tau           : ndarray (L,)              τ_ij ∈ [0, 1]
        gap           : ndarray (L,)              1 − τ_ij ∈ [0, 1]
        worst_branch  : str                       branch with largest gap
        worst_gap     : float                     max(1 − τ)
        max_abs_gap   : float                     same as worst_gap (alias)
    """
    if "Wr" not in socp_result.get("details", {}):
        _, _, names = _branch_pairs_and_names(circuit)
        nan_arr = np.full(len(names), np.nan)
        return dict(branch_names=names, tau=nan_arr, gap=nan_arr,
                    worst_branch=None, worst_gap=np.nan, max_abs_gap=np.nan)

    Wr_v = np.asarray(socp_result["details"]["Wr"])
    Wi_v = np.asarray(socp_result["details"]["Wi"])
    Wd_v = np.asarray(socp_result["details"].get("Wd",
                                                  socp_result["v_mag"] ** 2))

    _, pairs, names = _branch_pairs_and_names(circuit)
    L = len(pairs)
    tau = np.empty(L)
    for k, (i, j) in enumerate(pairs):
        denom = Wd_v[i] * Wd_v[j]
        tau[k] = (Wr_v[k] ** 2 + Wi_v[k] ** 2) / denom if denom > 0 else 0.0

    gap = 1.0 - tau
    worst = int(np.argmax(gap))
    return dict(
        branch_names=names,
        tau=tau,
        gap=gap,
        worst_branch=names[worst],
        worst_gap=float(gap[worst]),
        max_abs_gap=float(gap[worst]),
    )


def loop_residuals(circuit, socp_result) -> dict:
    """Angle residual around each fundamental cycle of the SOCP solution.

    For the BFS spanning tree from the slack, every non-tree branch closes
    exactly one fundamental cycle. The angle drop predicted by that branch's
    own W_ij (= arctan(Wi/Wr)) should match the angle drop predicted by the
    sum of tree-path drops between its endpoints. Any mismatch is the angle
    residual of that loop — a direct measurement of how far the relaxation
    drifts from a rank-1 solution.

    Returns
    -------
    dict with keys:
        non_tree_branches : list[str]    branch names that close a loop
        residuals_rad     : ndarray      residual per loop (radians, wrapped to ±π)
        residuals_deg     : ndarray      same in degrees
        max_abs_deg       : float        max |residual| across all loops (0 if radial)
    """
    if "Wr" not in socp_result.get("details", {}):
        return dict(non_tree_branches=[], residuals_rad=np.array([]),
                    residuals_deg=np.array([]), max_abs_deg=np.nan)

    Wr_v = np.asarray(socp_result["details"]["Wr"])
    Wi_v = np.asarray(socp_result["details"]["Wi"])

    bus_idx, pairs, names = _branch_pairs_and_names(circuit)
    N = len(bus_idx)

    slack_idx = next(bus_idx[name]
                     for name, b in circuit.buses.items()
                     if b.bus_type == BusType.Slack)

    adj = {n: [] for n in range(N)}
    for k, (i, j) in enumerate(pairs):
        adj[i].append((j, k, True))
        adj[j].append((i, k, False))

    # BFS from slack: assign tree angles and mark tree edges
    angles = np.zeros(N)
    visited = {slack_idx}
    queue = deque([slack_idx])
    tree_edges = set()
    while queue:
        n = queue.popleft()
        for nbr, k, fwd in adj[n]:
            if nbr in visited:
                continue
            visited.add(nbr)
            queue.append(nbr)
            tree_edges.add(k)
            arg_W = np.arctan2(Wi_v[k], Wr_v[k])
            # arg(W_ij) = θ_i − θ_j with i = stored br['i']
            angles[nbr] = angles[n] - arg_W if fwd else angles[n] + arg_W

    out_branches, residuals = [], []
    for k, (i, j) in enumerate(pairs):
        if k in tree_edges:
            continue
        direct = np.arctan2(Wi_v[k], Wr_v[k])     # θ_i − θ_j from this branch
        predicted = angles[i] - angles[j]          # θ_i − θ_j from tree path
        r = direct - predicted
        r = (r + np.pi) % (2 * np.pi) - np.pi      # wrap to (-π, π]
        out_branches.append(names[k])
        residuals.append(r)

    res_arr = np.array(residuals) if residuals else np.array([])
    return dict(
        non_tree_branches=out_branches,
        residuals_rad=res_arr,
        residuals_deg=np.degrees(res_arr),
        max_abs_deg=float(np.max(np.abs(np.degrees(res_arr)))) if len(res_arr) else 0.0,
    )
