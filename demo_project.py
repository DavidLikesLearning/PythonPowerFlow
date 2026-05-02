"""
Multi-grid OPF comparison driver.

Builds a power system as both a PythonPowerFlow Circuit and a pandapower
network, then solves it four ways and writes a side-by-side CSV:
    socp_pf   — our AC SOCP relaxation  (solve_socp, pf mode)
    dc_opf    — our linear DC OPF       (solve_dc_opf, opf mode)
    pp_acpf   — pandapower AC PF        (pp.runpp via solve_pandapower)
    pp_dcopf  — pandapower DC OPF       (pp.rundcopp via solve_pandapower)

Architecture
------------
* compare_solvers(circuit_factory, pandapower_factory, gen_limits, gen_costs,
                  output_csv) — grid-agnostic mother function. Pass any pair
  of zero-argument factory callables that build matching Circuit and
  pandapower networks, plus the per-generator limits and costs.
* Per-grid sections below each define the data, builders, and a thin
  wrapper compare_<gridname>() that hands them to compare_solvers().

Adding a new grid: see the IEEE 14-bus section as a template — define
BUS_DATA / BRANCH_DATA / GEN_DATA, write make_<grid>_circuit() and
make_<grid>_pandapower(), then a compare_<grid>() one-liner.
"""
from __future__ import annotations

import csv
import time
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandapower as pp

from bus import BusType
from circuit import Circuit
from opfs import (
    solve_socp, solve_dc_opf, solve_pandapower,
    branch_tightness, loop_residuals,
)

# ── IEEE 14-bus data (MATPOWER case14, per-unit on 100 MVA base) ───────────

VN_KV  = 138.0
SN_MVA = 100.0
F_HZ   = 60.0
Z_BASE = VN_KV ** 2 / SN_MVA
OMEGA  = 2 * np.pi * F_HZ

# (id, type, Pd_MW, Qd_MVAr, Vm_pu)   type ∈ {"slack","pv","pq"}
BUS_DATA: List[Tuple[int, str, float, float, float]] = [
    ( 1, "slack", 0.0,   0.0, 1.060),
    ( 2, "pv",   21.7,  12.7, 1.045),
    ( 3, "pv",   94.2,  19.0, 1.010),
    ( 4, "pq",   47.8,  -3.9, 1.000),
    ( 5, "pq",    7.6,   1.6, 1.000),
    ( 6, "pv",   11.2,   7.5, 1.070),
    ( 7, "pq",    0.0,   0.0, 1.000),
    ( 8, "pv",    0.0,   0.0, 1.090),
    ( 9, "pq",   29.5,  16.6, 1.000),
    (10, "pq",    9.0,   5.8, 1.000),
    (11, "pq",    3.5,   1.8, 1.000),
    (12, "pq",    6.1,   1.6, 1.000),
    (13, "pq",   13.5,   5.8, 1.000),
    (14, "pq",   14.9,   5.0, 1.000),
]

# (from, to, r_pu, x_pu, b_pu, kind)   kind ∈ {"line","tx"}
# Lines listed first, then transformers — matches opfs._extract_from_circuit
# branch ordering (transmission_lines then transformers).
BRANCH_DATA: List[Tuple[int, int, float, float, float, str]] = [
    ( 1,  2, 0.01938, 0.05917, 0.0528, "line"),
    ( 1,  5, 0.05403, 0.22304, 0.0492, "line"),
    ( 2,  3, 0.04699, 0.19797, 0.0438, "line"),
    ( 2,  4, 0.05811, 0.17632, 0.0340, "line"),
    ( 2,  5, 0.05695, 0.17388, 0.0346, "line"),
    ( 3,  4, 0.06701, 0.17103, 0.0128, "line"),
    ( 4,  5, 0.01335, 0.04211, 0.0000, "line"),
    ( 6, 11, 0.09498, 0.19890, 0.0000, "line"),
    ( 6, 12, 0.12291, 0.25581, 0.0000, "line"),
    ( 6, 13, 0.06615, 0.13027, 0.0000, "line"),
    ( 7,  8, 0.00000, 0.17615, 0.0000, "line"),
    ( 7,  9, 0.00000, 0.11001, 0.0000, "line"),
    ( 9, 10, 0.03181, 0.08450, 0.0000, "line"),
    ( 9, 14, 0.12711, 0.27038, 0.0000, "line"),
    (10, 11, 0.08205, 0.19207, 0.0000, "line"),
    (12, 13, 0.22092, 0.19988, 0.0000, "line"),
    (13, 14, 0.17093, 0.34802, 0.0000, "line"),
    ( 4,  7, 0.00000, 0.20912, 0.0000, "tx"),
    ( 4,  9, 0.00000, 0.55618, 0.0000, "tx"),
    ( 5,  6, 0.00000, 0.25202, 0.0000, "tx"),
]

# (name, bus, p_set_MW, p_min_MW, p_max_MW, q_min_MVAr, q_max_MVAr, cost_$/MWh)
# Q-limits are wider than canonical MATPOWER case14 to compensate for the
# omitted bus-9 shunt (see module docstring).
GEN_DATA: List[Tuple[str, int, float, float, float, float, float, float]] = [
    ("Gen1",  1, 232.4, 0.0, 332.4, -50.0,  50.0, 20.0),
    ("Gen2",  2,  40.0, 0.0, 140.0, -50.0, 100.0, 30.0),
    ("Gen3",  3,   0.0, 0.0, 100.0, -30.0,  60.0, 40.0),
    ("Gen6",  6,   0.0, 0.0, 100.0, -30.0,  60.0, 50.0),
    ("Gen8",  8,   0.0, 0.0, 100.0, -30.0,  60.0, 50.0),
]


def _bus_name(b: int) -> str:
    return f"Bus{b:02d}"


def _branch_name(fb: int, tb: int) -> str:
    return f"L{fb:02d}-{tb:02d}"


def make_gen_limits() -> Dict[str, Dict[str, float]]:
    """Generator limits dict for solve_socp / solve_dc_opf."""
    return {
        g[0]: {"p_min": g[3], "p_max": g[4], "q_min": g[5], "q_max": g[6]}
        for g in GEN_DATA
    }


def make_gen_costs() -> Dict[str, float]:
    """Linear generator costs ($/MWh) for both opf modes."""
    return {g[0]: g[7] for g in GEN_DATA}


# ── Builders (each is independently runnable) ──────────────────────────────

def make_case14_circuit() -> Circuit:
    """Build IEEE 14-bus as a PythonPowerFlow Circuit."""
    c = Circuit("IEEE_14_bus")

    type_map = {"slack": BusType.Slack, "pv": BusType.PV, "pq": BusType.PQ}
    for bid, btype, _, _, vm in BUS_DATA:
        c.add_bus(_bus_name(bid), VN_KV, type_map[btype], vpu=vm)

    for fb, tb, r, x, b, kind in BRANCH_DATA:
        name = _branch_name(fb, tb)
        if kind == "line":
            c.add_transmission_line(name, _bus_name(fb), _bus_name(tb),
                                    r=r, x=x, b=b)
        else:
            c.add_transformer(name, _bus_name(fb), _bus_name(tb), r=r, x=x)

    for bid, _, pd, qd, _ in BUS_DATA:
        if pd != 0.0 or qd != 0.0:
            c.add_load(f"Load{bid:02d}", _bus_name(bid), mw=pd, mvar=qd)

    bus_vm = {bid: vm for bid, _, _, _, vm in BUS_DATA}
    for name, bid, p_set, *_rest in GEN_DATA:
        c.add_generator(name, _bus_name(bid),
                        voltage_setpoint=bus_vm[bid],
                        mw_setpoint=p_set)
    return c


def make_case14_pandapower():
    """Build IEEE 14-bus in pandapower (physical units, all branches as lines)."""
    net = pp.create_empty_network(sn_mva=SN_MVA, f_hz=F_HZ)

    bus_pp: Dict[int, int] = {}
    for bid, _, _, _, _ in BUS_DATA:
        bus_pp[bid] = pp.create_bus(net, VN_KV, name=_bus_name(bid))

    slack_bid = next(bid for bid, t, *_ in BUS_DATA if t == "slack")
    bus_vm = {bid: vm for bid, _, _, _, vm in BUS_DATA}
    slack_gen = next(g for g in GEN_DATA if g[1] == slack_bid)
    pp.create_ext_grid(
        net, bus_pp[slack_bid], vm_pu=bus_vm[slack_bid],
        name=slack_gen[0],
        min_p_mw=slack_gen[3], max_p_mw=slack_gen[4],
        min_q_mvar=slack_gen[5], max_q_mvar=slack_gen[6],
    )

    for name, bid, p_set, p_min, p_max, q_min, q_max, _ in GEN_DATA:
        if bid == slack_bid:
            continue
        pp.create_gen(
            net, bus_pp[bid], p_mw=p_set, vm_pu=bus_vm[bid], name=name,
            min_p_mw=p_min, max_p_mw=p_max,
            min_q_mvar=q_min, max_q_mvar=q_max,
        )

    for bid, _, pd, qd, _ in BUS_DATA:
        if pd != 0.0 or qd != 0.0:
            pp.create_load(net, bus_pp[bid], p_mw=pd, q_mvar=qd,
                           name=f"Load{bid:02d}")

    for fb, tb, r_pu, x_pu, b_pu, _ in BRANCH_DATA:
        c_nf = b_pu * 1e9 / (Z_BASE * OMEGA) if b_pu > 0 else 0.0
        pp.create_line_from_parameters(
            net, bus_pp[fb], bus_pp[tb], length_km=1.0,
            r_ohm_per_km=r_pu * Z_BASE,
            x_ohm_per_km=x_pu * Z_BASE,
            c_nf_per_km=c_nf, max_i_ka=10.0,
            name=_branch_name(fb, tb),
        )
    return net


# ── Individual runners (each independent) ─────────────────────────────────

def run_socp_pf() -> dict:
    """Run our SOCP relaxation in pf mode against the case14 Circuit."""
    return solve_socp(make_case14_circuit(), mode="pf",
                      gen_limits=make_gen_limits(),
                      gen_costs=make_gen_costs())


def run_dc_opf() -> dict:
    """Run our linear DC OPF against the case14 Circuit."""
    return solve_dc_opf(make_case14_circuit(), mode="opf",
                        gen_limits=make_gen_limits(),
                        gen_costs=make_gen_costs())


def run_pandapower_acpf() -> dict:
    """Run pandapower Newton-Raphson AC PF against the case14 net."""
    return solve_pandapower(make_case14_pandapower(), mode="pf")


def run_pandapower_dcopf() -> dict:
    """Run pandapower DC OPF against the case14 net."""
    return solve_pandapower(make_case14_pandapower(), mode="opf",
                            gen_costs=make_gen_costs())


# ── Generic comparison driver (grid-agnostic) ─────────────────────────────

_LABELS_MODES: List[Tuple[str, str]] = [
    ("socp_pf",  "pf"),
    ("dc_opf",   "opf"),
    ("pp_acpf",  "pf"),
    ("pp_dcopf", "opf"),
]


def _align_by_name(values: np.ndarray, src_names: List[str],
                   target_names: List[str]) -> np.ndarray:
    idx = {n: i for i, n in enumerate(src_names)}
    return np.array([values[idx[n]] if n in idx else np.nan
                     for n in target_names])


def _format_num(x) -> str:
    if isinstance(x, (int, float)) and not (isinstance(x, float) and np.isnan(x)):
        return f"{x:.6f}"
    return ""


def _circuit_branch_order(circuit: Circuit) -> List[str]:
    """opfs._extract_from_circuit orders branches: lines first, then transformers."""
    return list(circuit.transmission_lines.keys()) + list(circuit.transformers.keys())


def compare_solvers(
    circuit_factory: Callable[[], Circuit],
    pandapower_factory: Callable[[], "pp.pandapowerNet"],
    gen_limits: Dict[str, Dict[str, float]],
    gen_costs: Dict[str, float],
    output_csv: str = "comparison.csv",
    socp_mode: str = "pf",
    include_pp_acopf: bool = False,
    v_min: float = 0.5,
    v_max: float = 1.5,
    bus_order: List[str] | None = None,
    branch_order: List[str] | None = None,
) -> Dict[str, dict]:
    """Run solvers on any grid and write a side-by-side CSV.

    Parameters
    ----------
    circuit_factory      : zero-arg callable returning a populated Circuit
    pandapower_factory   : zero-arg callable returning a matching pandapower net
    gen_limits, gen_costs: passed to solve_socp / solve_dc_opf
    output_csv           : output path; four CSV sections (summary, buses,
                           branches, SOCP tightness)
    socp_mode            : "pf" (fix PV dispatch) or "opf" (minimise cost);
                           use "opf" for cases with a known relaxation gap
    include_pp_acopf     : if True, add a 5th solver column via pp.runopp;
                           lets you compare the SOCP lower bound to the true
                           AC OPF cost on non-convex cases (e.g. WB5)
    v_min, v_max         : voltage bounds passed to solve_socp (pu)
    bus_order, branch_order : canonical orderings for the CSV; default to
                           the Circuit's natural ordering

    Returns
    -------
    dict {solver_label: result_dict} — also contains "_labels_modes" and
    "_socp_tightness" metadata keys for use by print_summary().
    """
    socp_label = f"socp_{socp_mode}"
    labels_modes: List[Tuple[str, str]] = [
        (socp_label,  socp_mode),
        ("dc_opf",    "opf"),
        ("pp_acpf",   "pf"),
        ("pp_dcopf",  "opf"),
    ]
    if include_pp_acopf:
        labels_modes.append(("pp_acopf", "acopf"))

    results: Dict[str, dict] = {
        socp_label: solve_socp(circuit_factory(), mode=socp_mode,
                               gen_limits=gen_limits, gen_costs=gen_costs,
                               v_min=v_min, v_max=v_max),
        "dc_opf":   solve_dc_opf(circuit_factory(), mode="opf",
                                 gen_limits=gen_limits, gen_costs=gen_costs),
        "pp_acpf":  solve_pandapower(pandapower_factory(), mode="pf"),
        "pp_dcopf": solve_pandapower(pandapower_factory(), mode="opf",
                                     gen_costs=gen_costs),
    }
    if include_pp_acopf:
        results["pp_acopf"] = solve_pandapower(
            pandapower_factory(), mode="acopf", gen_costs=gen_costs
        )

    # Source orderings each solver returns results in
    _circ = circuit_factory()
    circuit_bus_order = list(_circ.calc_ybus().index)
    circuit_branch_order = _circuit_branch_order(_circ)
    _net = pandapower_factory()
    pp_bus_order = _net.bus["name"].tolist()
    pp_branch_order = _net.line["name"].tolist()

    src = {lbl: (circuit_bus_order, circuit_branch_order)
           if lbl in (socp_label, "dc_opf")
           else (pp_bus_order, pp_branch_order)
           for lbl, _ in labels_modes}

    bus_target = bus_order if bus_order is not None else circuit_bus_order
    branch_target = branch_order if branch_order is not None else circuit_branch_order

    with open(output_csv, "w", newline="") as f:
        w = csv.writer(f)

        # ── Section 1: summary ─────────────────────────────────────────────
        w.writerow(["solver", "mode", "converged", "solve_time_s", "obj_val"])
        for label, mode in labels_modes:
            r = results[label]
            t = r["details"].get("solve_time_s", None)
            obj = r["details"].get("obj_val", None)
            w.writerow([label, mode, r["converged"],
                        _format_num(t), _format_num(obj)])
        w.writerow([])

        # ── Section 2: bus voltages ─────────────────────────────────────────
        header = ["bus_name"]
        header += [f"{lbl}_vmag" for lbl, _ in labels_modes]
        header += [f"{lbl}_vang_deg" for lbl, _ in labels_modes]
        w.writerow(header)

        aligned_vmag = {lbl: _align_by_name(results[lbl]["v_mag"],
                                             src[lbl][0], bus_target)
                        for lbl, _ in labels_modes}
        aligned_vang = {lbl: _align_by_name(results[lbl]["v_ang_deg"],
                                             src[lbl][0], bus_target)
                        for lbl, _ in labels_modes}
        for i, name in enumerate(bus_target):
            row = [name]
            for lbl, _ in labels_modes:
                row.append(_format_num(aligned_vmag[lbl][i]))
            for lbl, _ in labels_modes:
                row.append(_format_num(aligned_vang[lbl][i]))
            w.writerow(row)
        w.writerow([])

        # ── Section 3: branch flows (from-end pu) ──────────────────────────
        header = ["branch_name"]
        header += [f"{lbl}_p_from_pu" for lbl, _ in labels_modes]
        header += [f"{lbl}_q_from_pu" for lbl, _ in labels_modes]
        w.writerow(header)

        aligned_p = {lbl: _align_by_name(results[lbl]["p_fr"],
                                          src[lbl][1], branch_target)
                     for lbl, _ in labels_modes}
        aligned_q = {lbl: _align_by_name(results[lbl]["q_fr"],
                                          src[lbl][1], branch_target)
                     for lbl, _ in labels_modes}
        for i, name in enumerate(branch_target):
            row = [name]
            for lbl, _ in labels_modes:
                row.append(_format_num(aligned_p[lbl][i]))
            for lbl, _ in labels_modes:
                row.append(_format_num(aligned_q[lbl][i]))
            w.writerow(row)
        w.writerow([])

        # ── Section 4: SOCP tightness per branch ───────────────────────────
        socp_result = results[socp_label]
        tight = branch_tightness(circuit_factory(), socp_result)
        loops = loop_residuals(circuit_factory(), socp_result)
        loop_lookup = dict(zip(loops["non_tree_branches"], loops["residuals_deg"]))
        tau_by_name = dict(zip(tight["branch_names"], tight["tau"]))

        w.writerow(["branch_name", "tau", "gap_1_minus_tau",
                    "in_loop", "loop_residual_deg"])
        for name in branch_target:
            tau_v = tau_by_name.get(name, np.nan)
            gap_v = 1.0 - tau_v if not np.isnan(tau_v) else np.nan
            in_loop = "yes" if name in loop_lookup else "no"
            res_v = loop_lookup.get(name, "")
            w.writerow([
                name, _format_num(tau_v), _format_num(gap_v),
                in_loop, _format_num(res_v) if res_v != "" else "",
            ])

    results["_labels_modes"] = labels_modes
    results["_socp_tightness"] = dict(
        max_gap=tight["worst_gap"],
        worst_branch=tight["worst_branch"],
        max_loop_residual_deg=loops["max_abs_deg"],
        branch_names=tight["branch_names"],
        tau=tight["tau"],
        loop_residuals_deg=dict(zip(loops["non_tree_branches"],
                                    loops["residuals_deg"])),
    )
    return results


def print_summary(results: Dict[str, dict], grid_label: str = "") -> None:
    """Pretty-print the solver summary table to stdout."""
    labels_modes = results.get("_labels_modes", _LABELS_MODES)
    title = f"Comparison: {grid_label}" if grid_label else "Comparison"
    print(title)
    print(f"{'solver':<12} {'mode':<6} {'converged':<10} "
          f"{'time (s)':>10} {'obj':>12}")
    print("-" * 57)
    for label, mode in labels_modes:
        r = results[label]
        t = r["details"].get("solve_time_s", float("nan"))
        obj = r["details"].get("obj_val", "")
        obj_str = f"{obj:>12.4f}" if isinstance(obj, (int, float)) else " " * 12
        t_str = f"{t:>10.4f}" if isinstance(t, (int, float)) else " " * 10
        print(f"{label:<12} {mode:<6} {str(r['converged']):<10} "
              f"{t_str} {obj_str}")

    tight = results.get("_socp_tightness")
    if tight is not None:
        print()
        max_gap = tight["max_gap"]
        if tight["worst_branch"] is None or (isinstance(max_gap, float) and np.isnan(max_gap)):
            print("SOCP relaxation diagnostics: SOCP did not converge — no tightness data")
        else:
            print("SOCP relaxation diagnostics:")
            print(f"  max(1 − τ)   = {max_gap:.3e}   "
                  f"(worst branch: {tight['worst_branch']})")
            print(f"  max |loop Δ| = {tight['max_loop_residual_deg']:.4f}°")


# ── Per-grid wrappers ─────────────────────────────────────────────────────

def compare_case14(output_csv: str = "case14_comparison.csv") -> Dict[str, dict]:
    """Convenience wrapper: run the comparison on IEEE 14-bus."""
    return compare_solvers(
        make_case14_circuit, make_case14_pandapower,
        make_gen_limits(), make_gen_costs(),
        output_csv=output_csv,
    )


# Back-compat alias for the original name
compare_all_solvers = compare_case14


# ── WB5 (Bukhsh et al. 2013) ──────────────────────────────────────────────
# 5-bus meshed system with a documented SOCP relaxation duality gap.
# Gen at Bus5 (cost $1/MWh) is 4x cheaper than Gen at Bus1 (cost $4/MWh).
# The cheap generator is only reachable via two high-impedance paths (L02-04
# and L03-05), creating a non-convex bottleneck that the SOCP exploits.
# Reference: Bukhsh, Grothey, McKinnon, Trodden — IEEE Trans. Power Systems 2013.

VN_KV_WB5 = 345.0
Z_BASE_WB5 = VN_KV_WB5 ** 2 / SN_MVA

# (id, type, Pd_MW, Qd_MVAr, Vm_pu, Vmax, Vmin)
BUS_DATA_WB5: List[Tuple] = [
    (1, "slack", 0.0,   0.0, 1.0, 1.05, 0.95),
    (2, "pq",  130.0,  20.0, 1.0, 1.05, 0.95),
    (3, "pq",  130.0,  20.0, 1.0, 1.05, 0.95),
    (4, "pq",   65.0,  10.0, 1.0, 1.05, 0.95),
    (5, "pv",    0.0,   0.0, 1.0, 1.05, 0.95),
]

# (from, to, r_pu, x_pu, b_pu, kind)
BRANCH_DATA_WB5: List[Tuple] = [
    (1, 2, 0.04, 0.09, 0.00, "line"),
    (1, 3, 0.05, 0.10, 0.00, "line"),
    (2, 4, 0.55, 0.90, 0.45, "line"),
    (3, 5, 0.55, 0.90, 0.45, "line"),
    (4, 5, 0.06, 0.10, 0.00, "line"),
    (2, 3, 0.07, 0.09, 0.00, "line"),
]

# (name, bus, p_set_MW, p_min, p_max, q_min, q_max, cost_$/MWh)
GEN_DATA_WB5: List[Tuple] = [
    ("GenSlack", 1, 325.0, 0.0, 5000.0, -30.0, 1800.0, 4.0),
    ("GenPV",    5,   0.0, 0.0, 5000.0, -30.0, 1800.0, 1.0),
]


def make_wb5_gen_limits() -> Dict[str, Dict[str, float]]:
    return {g[0]: {"p_min": g[3], "p_max": g[4],
                   "q_min": g[5], "q_max": g[6]} for g in GEN_DATA_WB5}


def make_wb5_gen_costs() -> Dict[str, float]:
    return {g[0]: g[7] for g in GEN_DATA_WB5}


def make_wb5_circuit() -> Circuit:
    """Build the WB5 Bukhsh case as a PythonPowerFlow Circuit."""
    c = Circuit("WB5")
    type_map = {"slack": BusType.Slack, "pv": BusType.PV, "pq": BusType.PQ}
    for bid, btype, _, _, vm, *_ in BUS_DATA_WB5:
        c.add_bus(_bus_name(bid), VN_KV_WB5, type_map[btype], vpu=vm)

    for fb, tb, r, x, b, kind in BRANCH_DATA_WB5:
        name = _branch_name(fb, tb)
        if kind == "line":
            c.add_transmission_line(name, _bus_name(fb), _bus_name(tb),
                                    r=r, x=x, b=b)
        else:
            c.add_transformer(name, _bus_name(fb), _bus_name(tb), r=r, x=x)

    for bid, _, pd, qd, *_ in BUS_DATA_WB5:
        if pd != 0.0 or qd != 0.0:
            c.add_load(f"Load{bid:02d}", _bus_name(bid), mw=pd, mvar=qd)

    bus_vm = {bid: vm for bid, _, _, _, vm, *_ in BUS_DATA_WB5}
    for name, bid, p_set, *_rest in GEN_DATA_WB5:
        c.add_generator(name, _bus_name(bid),
                        voltage_setpoint=bus_vm[bid], mw_setpoint=p_set)
    return c


def make_wb5_pandapower(vmax_pu: float | None = None, vmin_pu: float | None = None):
    """Build the WB5 case in pandapower.

    vmax_pu / vmin_pu override the per-bus limits from BUS_DATA_WB5.
    Pass 1.5/0.5 for the OPF comparison (the natural operating point
    has PQ bus voltages below 0.95, so the canonical limits make OPF infeasible).
    """
    net = pp.create_empty_network(sn_mva=SN_MVA, f_hz=F_HZ)

    bus_pp: Dict[int, int] = {}
    for bid, _, _, _, _, vmax, vmin in BUS_DATA_WB5:
        bus_pp[bid] = pp.create_bus(net, VN_KV_WB5, name=_bus_name(bid),
                                    max_vm_pu=vmax_pu if vmax_pu is not None else vmax,
                                    min_vm_pu=vmin_pu if vmin_pu is not None else vmin)

    slack_bid = next(bid for bid, t, *_ in BUS_DATA_WB5 if t == "slack")
    bus_vm = {bid: vm for bid, _, _, _, vm, *_ in BUS_DATA_WB5}
    slack_gen = next(g for g in GEN_DATA_WB5 if g[1] == slack_bid)
    pp.create_ext_grid(
        net, bus_pp[slack_bid], vm_pu=bus_vm[slack_bid],
        name=slack_gen[0],
        min_p_mw=slack_gen[3], max_p_mw=slack_gen[4],
        min_q_mvar=slack_gen[5], max_q_mvar=slack_gen[6],
    )

    for name, bid, p_set, p_min, p_max, q_min, q_max, _ in GEN_DATA_WB5:
        if bid == slack_bid:
            continue
        pp.create_gen(
            net, bus_pp[bid], p_mw=p_set, vm_pu=bus_vm[bid], name=name,
            min_p_mw=p_min, max_p_mw=p_max,
            min_q_mvar=q_min, max_q_mvar=q_max,
        )

    for bid, _, pd, qd, *_ in BUS_DATA_WB5:
        if pd != 0.0 or qd != 0.0:
            pp.create_load(net, bus_pp[bid], p_mw=pd, q_mvar=qd,
                           name=f"Load{bid:02d}")

    for fb, tb, r_pu, x_pu, b_pu, _ in BRANCH_DATA_WB5:
        c_nf = b_pu * 1e9 / (Z_BASE_WB5 * OMEGA) if b_pu > 0 else 0.0
        pp.create_line_from_parameters(
            net, bus_pp[fb], bus_pp[tb], length_km=1.0,
            r_ohm_per_km=r_pu * Z_BASE_WB5,
            x_ohm_per_km=x_pu * Z_BASE_WB5,
            c_nf_per_km=c_nf, max_i_ka=10.0,
            name=_branch_name(fb, tb),
        )
    return net


def compare_wb5(output_csv: str = "wb5_comparison.csv") -> Dict[str, dict]:
    """Run all solvers on WB5 and write the comparison CSV.

    Uses socp_mode='opf' and include_pp_acopf=True to expose the duality gap:
    the SOCP lower bound is strictly below the true (pp.runopp) AC OPF cost.

    Voltage bounds are intentionally loose [0.5, 1.5] because the natural AC
    operating point for WB5 (high-impedance lines, large loads) has PQ bus
    voltages below 0.95 pu — the canonical Vmin makes both SOCP and AC OPF
    infeasible.  The duality gap is a property of the network topology and
    costs, not of the voltage bounds.
    """
    return compare_solvers(
        make_wb5_circuit,
        lambda: make_wb5_pandapower(vmax_pu=1.5, vmin_pu=0.5),
        make_wb5_gen_limits(), make_wb5_gen_costs(),
        output_csv=output_csv,
        socp_mode="opf",
        include_pp_acopf=True,
        v_min=0.5, v_max=1.5,
    )


# ── Case22loop (Bukhsh et al. 2013) ──────────────────────────────────────
# 22-bus ring network with alternating generator and load buses.
# All 11 generators share the same linear cost ($2/MWh), so the OPF has
# multiple local optima differing in the direction and split of power flow
# around the ring.  Reference: Bukhsh et al., IEEE Trans. Power Systems 2013.

VN_KV_C22 = 345.0
Z_BASE_C22 = VN_KV_C22 ** 2 / SN_MVA

_C22_PD   = 95.0 * 2.15    # 204.25 MW per load bus (MATPOWER scaling factor)
_C22_QD   = 20.0 * 2.15    # 43.00 MVAr per load bus

# (id, type, Pd_MW, Qd_MVAr, Vm_pu)
# Odd buses: slack (1) or PV with generator; even buses: PQ with load.
BUS_DATA_C22: List[Tuple] = [
    (1,  "slack", 0.0,     0.0,    1.0),
    (2,  "pq",  _C22_PD, _C22_QD, 0.95),
    (3,  "pv",    0.0,     0.0,    1.0),
    (4,  "pq",  _C22_PD, _C22_QD, 0.95),
    (5,  "pv",    0.0,     0.0,    1.0),
    (6,  "pq",  _C22_PD, _C22_QD, 0.95),
    (7,  "pv",    0.0,     0.0,    1.0),
    (8,  "pq",  _C22_PD, _C22_QD, 0.95),
    (9,  "pv",    0.0,     0.0,    1.0),
    (10, "pq",  _C22_PD, _C22_QD, 0.95),
    (11, "pv",    0.0,     0.0,    1.0),
    (12, "pq",  _C22_PD, _C22_QD, 0.95),
    (13, "pv",    0.0,     0.0,    1.0),
    (14, "pq",  _C22_PD, _C22_QD, 0.95),
    (15, "pv",    0.0,     0.0,    1.0),
    (16, "pq",  _C22_PD, _C22_QD, 0.95),
    (17, "pv",    0.0,     0.0,    1.0),
    (18, "pq",  _C22_PD, _C22_QD, 0.95),
    (19, "pv",    0.0,     0.0,    1.0),
    (20, "pq",  _C22_PD, _C22_QD, 0.95),
    (21, "pv",    0.0,     0.0,    1.0),
    (22, "pq",  _C22_PD, _C22_QD, 0.95),
]

# Ring: 1-2, 2-3, ..., 21-22, 22-1  (i % 22 + 1 wraps 22 → 1)
BRANCH_DATA_C22: List[Tuple] = [
    (i, i % 22 + 1, 0.01, 0.05, 0.0, "line")
    for i in range(1, 23)
]

# (name, bus, p_set_MW, p_min, p_max, q_min, q_max, cost_$/MWh)
# All generators identical cost; p_set = equal-share dispatch as PF starting point.
GEN_DATA_C22: List[Tuple] = [
    (f"Gen{bid:02d}", bid, _C22_PD, 0.0, 10000.0, -20000.0, 20000.0, 2.0)
    for bid in range(1, 23, 2)   # 1, 3, 5, ..., 21
]


def make_c22loop_gen_limits() -> Dict[str, Dict[str, float]]:
    return {g[0]: {"p_min": g[3], "p_max": g[4],
                   "q_min": g[5], "q_max": g[6]} for g in GEN_DATA_C22}


def make_c22loop_gen_costs() -> Dict[str, float]:
    return {g[0]: g[7] for g in GEN_DATA_C22}


def make_c22loop_circuit() -> Circuit:
    """Build the 22-bus Bukhsh ring case as a PythonPowerFlow Circuit."""
    c = Circuit("Case22loop")
    type_map = {"slack": BusType.Slack, "pv": BusType.PV, "pq": BusType.PQ}
    for bid, btype, _, _, vm in BUS_DATA_C22:
        c.add_bus(_bus_name(bid), VN_KV_C22, type_map[btype], vpu=vm)

    for fb, tb, r, x, b, _ in BRANCH_DATA_C22:
        c.add_transmission_line(_branch_name(fb, tb), _bus_name(fb), _bus_name(tb),
                                r=r, x=x, b=b)

    for bid, _, pd, qd, _ in BUS_DATA_C22:
        if pd != 0.0 or qd != 0.0:
            c.add_load(f"Load{bid:02d}", _bus_name(bid), mw=pd, mvar=qd)

    bus_vm = {bid: vm for bid, _, _, _, vm in BUS_DATA_C22}
    for name, bid, p_set, *_rest in GEN_DATA_C22:
        c.add_generator(name, _bus_name(bid),
                        voltage_setpoint=bus_vm[bid], mw_setpoint=p_set)
    return c


def make_c22loop_pandapower(vmax_pu: float = 1.05, vmin_pu: float = 0.95):
    """Build the 22-bus ring case in pandapower.

    vmax_pu / vmin_pu set the OPF voltage bounds on every bus.  Pass 1.5/0.5
    if the SOCP or pp.runopp becomes infeasible with canonical [0.95, 1.05].
    """
    net = pp.create_empty_network(sn_mva=SN_MVA, f_hz=F_HZ)

    bus_pp: Dict[int, int] = {}
    for bid, *_ in BUS_DATA_C22:
        bus_pp[bid] = pp.create_bus(net, VN_KV_C22, name=_bus_name(bid),
                                    max_vm_pu=vmax_pu, min_vm_pu=vmin_pu)

    bus_vm = {bid: vm for bid, _, _, _, vm in BUS_DATA_C22}
    slack_gen = next(g for g in GEN_DATA_C22 if g[1] == 1)
    pp.create_ext_grid(
        net, bus_pp[1], vm_pu=bus_vm[1], name=slack_gen[0],
        min_p_mw=slack_gen[3], max_p_mw=slack_gen[4],
        min_q_mvar=slack_gen[5], max_q_mvar=slack_gen[6],
    )

    for name, bid, p_set, p_min, p_max, q_min, q_max, _ in GEN_DATA_C22:
        if bid == 1:
            continue
        pp.create_gen(net, bus_pp[bid], p_mw=p_set, vm_pu=bus_vm[bid], name=name,
                      min_p_mw=p_min, max_p_mw=p_max,
                      min_q_mvar=q_min, max_q_mvar=q_max)

    for bid, _, pd, qd, _ in BUS_DATA_C22:
        if pd != 0.0 or qd != 0.0:
            pp.create_load(net, bus_pp[bid], p_mw=pd, q_mvar=qd,
                           name=f"Load{bid:02d}")

    for fb, tb, r_pu, x_pu, b_pu, _ in BRANCH_DATA_C22:
        c_nf = b_pu * 1e9 / (Z_BASE_C22 * OMEGA) if b_pu > 0 else 0.0
        pp.create_line_from_parameters(
            net, bus_pp[fb], bus_pp[tb], length_km=1.0,
            r_ohm_per_km=r_pu * Z_BASE_C22,
            x_ohm_per_km=x_pu * Z_BASE_C22,
            c_nf_per_km=c_nf, max_i_ka=10.0,
            name=_branch_name(fb, tb),
        )
    return net


def make_c22loop_asym_gen_costs() -> Dict[str, float]:
    """Asymmetric costs: generators on buses 1-11 at $1/MWh (cheap arc),
    buses 13-21 at $4/MWh (expensive arc).

    Splitting the ring into a cheap arc and an expensive arc forces the OPF to
    choose how to route power from cheap to distant loads — two topologically
    distinct paths (clockwise and counterclockwise around the ring) each
    constitute a different local AC OPF solution.
    """
    return {g[0]: 1.0 if g[1] <= 11 else 4.0 for g in GEN_DATA_C22}


def compare_c22loop(output_csv: str = "c22loop_comparison.csv") -> Dict:
    """Run all solvers on Case22loop and write the comparison CSV.

    Uses socp_mode='opf' and include_pp_acopf=True to expose the cost structure.
    Voltage bounds are the canonical [0.95, 1.05]; generators are co-located with
    loads around the ring, so voltages stay well-controlled.
    """
    return compare_solvers(
        make_c22loop_circuit,
        lambda: make_c22loop_pandapower(vmax_pu=1.05, vmin_pu=0.95),
        make_c22loop_gen_limits(), make_c22loop_gen_costs(),
        output_csv=output_csv,
        socp_mode="opf",
        include_pp_acopf=True,
        v_min=0.95, v_max=1.05,
    )


def compare_c22loop_asym(output_csv: str = "c22loop_asym_comparison.csv") -> Dict:
    """Run all solvers on Case22loop with asymmetric generator costs.

    Cheap arc (buses 1,3,5,7,9,11 at $1/MWh) vs expensive arc (buses 13-21
    at $4/MWh).  With canonical [0.95,1.05] voltage limits the cheap generators
    cannot serve the full load unassisted — voltage drops force some expensive
    dispatch, creating a genuine duality gap and multiple local AC solutions.
    """
    return compare_solvers(
        make_c22loop_circuit,
        lambda: make_c22loop_pandapower(vmax_pu=1.05, vmin_pu=0.95),
        make_c22loop_gen_limits(), make_c22loop_asym_gen_costs(),
        output_csv=output_csv,
        socp_mode="opf",
        include_pp_acopf=True,
        v_min=0.95, v_max=1.05,
    )


# ── Multi-start local-solutions demonstration ─────────────────────────────


def _run_nr_from_init(pandapower_factory: Callable,
                      v_init_arr: np.ndarray,
                      ang_init_arr_deg: np.ndarray) -> dict:
    """Run pandapower NR from a custom (|V|, θ) starting point.

    Injects v_init_arr / ang_init_arr_deg into net.res_bus, then calls
    pp.runpp(init="results") so Newton–Raphson iterates from that point.
    The slack bus angle is fixed at 0° by pandapower regardless.

    Returns a result dict in the standard schema plus details keys
    ``v_init``, ``ang_init_deg``, ``p_ext_grid_mw``, ``p_gen_mw``.
    """
    import pandas as pd

    net = pandapower_factory()
    sn_mva = float(net.sn_mva)
    n_bus = len(net.bus)

    # Warm the network to create net.res_bus (used by init="results").
    # Non-convergence here is fine — we just need the DataFrame structure.
    try:
        pp.runpp(net, init="flat", max_iteration=50, verbose=False)
    except Exception:
        pass

    if len(net.res_bus) != n_bus:
        net["res_bus"] = pd.DataFrame(
            {"vm_pu": np.ones(n_bus), "va_degree": np.zeros(n_bus),
             "p_mw": np.zeros(n_bus), "q_mvar": np.zeros(n_bus)},
            index=net.bus.index,
        )

    net.res_bus["vm_pu"] = v_init_arr
    net.res_bus["va_degree"] = ang_init_arr_deg

    t0 = time.perf_counter()
    try:
        pp.runpp(net, algorithm="nr", calculate_voltage_angles=True,
                 init="results", max_iteration=50, verbose=False)
        converged = bool(net["converged"])
    except Exception as e:
        elapsed = time.perf_counter() - t0
        L = len(net.line)
        return {
            "source": "pandapower_nr", "converged": False,
            "v_mag": np.array(v_init_arr), "v_ang_deg": np.array(ang_init_arr_deg),
            "p_fr": np.zeros(L), "q_fr": np.zeros(L),
            "p_to": np.zeros(L), "q_to": np.zeros(L),
            "details": {"message": str(e), "solve_time_s": time.perf_counter() - t0,
                        "backend_used": "pandapower",
                        "v_init": v_init_arr.tolist(),
                        "ang_init_deg": ang_init_arr_deg.tolist()},
        }

    elapsed = time.perf_counter() - t0
    L = len(net.line)

    if not converged:
        return {
            "source": "pandapower_nr", "converged": False,
            "v_mag": np.array(v_init_arr), "v_ang_deg": np.array(ang_init_arr_deg),
            "p_fr": np.zeros(L), "q_fr": np.zeros(L),
            "p_to": np.zeros(L), "q_to": np.zeros(L),
            "details": {"message": "NR did not converge", "solve_time_s": elapsed,
                        "backend_used": "pandapower",
                        "v_init": v_init_arr.tolist(),
                        "ang_init_deg": ang_init_arr_deg.tolist()},
        }

    return {
        "source": "pandapower_nr",
        "v_mag": net.res_bus["vm_pu"].values.copy(),
        "v_ang_deg": net.res_bus["va_degree"].values.copy(),
        "p_fr": net.res_line["p_from_mw"].values.copy() / sn_mva,
        "q_fr": net.res_line["q_from_mvar"].values.copy() / sn_mva,
        "p_to": net.res_line["p_to_mw"].values.copy() / sn_mva,
        "q_to": net.res_line["q_to_mvar"].values.copy() / sn_mva,
        "converged": True,
        "details": {
            "solve_time_s": elapsed,
            "backend_used": "pandapower",
            "p_ext_grid_mw": net.res_ext_grid["p_mw"].values.tolist(),
            "p_gen_mw": net.res_gen["p_mw"].values.tolist(),
            "v_init": v_init_arr.tolist(),
            "ang_init_deg": ang_init_arr_deg.tolist(),
        },
    }


def _cluster_nr_solutions(nr_runs: List[dict],
                           tol_v: float = 0.05) -> Tuple[List, List[dict]]:
    """Greedy clustering of converged NR runs by voltage-magnitude profile.

    Two runs are in the same cluster when their |V| vectors differ by less than
    tol_v in the max-norm (pu).  Non-converged runs get cluster ID None.

    Returns
    -------
    cluster_ids : list[int | None]
    clusters    : list[dict]  — representative result per cluster
    """
    cluster_ids: List = [None] * len(nr_runs)
    clusters: List[dict] = []
    for i, r in enumerate(nr_runs):
        if not r["converged"]:
            continue
        vm = r["v_mag"]
        for cid, rep in enumerate(clusters):
            if np.max(np.abs(vm - rep["v_mag"])) < tol_v:
                cluster_ids[i] = cid
                break
        else:
            cluster_ids[i] = len(clusters)
            clusters.append(r)
    return cluster_ids, clusters


def _gen_cost_from_nr(nr_result: dict, net_ref,
                      gen_costs: Dict[str, float]) -> Optional[float]:
    """Compute total generation cost ($/h) from a converged NR result dict."""
    if not gen_costs or not nr_result.get("converged"):
        return None
    obj = 0.0
    p_ext = nr_result["details"].get("p_ext_grid_mw", [])
    p_gen = nr_result["details"].get("p_gen_mw", [])
    for i, (_, row) in enumerate(net_ref.ext_grid.iterrows()):
        name = row.get("name", f"ext_grid_{i}")
        if name in gen_costs and i < len(p_ext):
            obj += p_ext[i] * gen_costs[name]
    for i, (_, row) in enumerate(net_ref.gen.iterrows()):
        name = row.get("name", f"gen_{i}")
        if name in gen_costs and i < len(p_gen):
            obj += p_gen[i] * gen_costs[name]
    return obj


def multi_start_comparison(
    circuit_factory: Callable[[], Circuit],
    pandapower_factory: Callable[[], "pp.pandapowerNet"],
    gen_limits: Dict[str, Dict[str, float]],
    gen_costs: Dict[str, float],
    n_starts: int = 20,
    v_range: Tuple[float, float] = (1.0, 1.5),
    angle_range: Tuple[float, float] = (-60.0, 60.0),
    seed: int = 42,
    socp_mode: str = "pf",
    v_min: float = 0.5,
    v_max: float = 1.5,
    tol_v_cluster: float = 0.02,
) -> Dict:
    """Run NR from n_starts random high-V / high-angle starting points to reveal
    multiple local AC solutions.  SOCP and DC OPF are run once (convex —
    their solution is independent of the starting point).

    Random starting voltages are drawn uniformly from v_range (pu) and angles
    from angle_range (degrees) independently for every bus.  The slack bus
    angle is always overridden to 0° by pandapower.

    Parameters
    ----------
    n_starts      : number of random NR starting points
    v_range       : (v_lo, v_hi) pu — uniform range for initial |V| per bus
    angle_range   : (a_lo, a_hi) degrees — uniform range for initial θ per bus
    seed          : RNG seed for reproducibility
    socp_mode     : "pf" or "opf" — passed to solve_socp
    v_min, v_max  : voltage bounds for SOCP (pu)
    tol_v_cluster : max-norm tolerance (pu) to group NR solutions into clusters;
                    0.02 separates solutions that differ by ≥20 mV at any bus

    Returns
    -------
    dict with keys:
        socp, dc_opf      — single-run convex solver results
        nr_runs           — list of n_starts NR result dicts
        nr_cluster_ids    — list[int | None], cluster assignment per run
        nr_clusters       — list of representative dicts (one per distinct solution)
        nr_obj_vals       — list[float | None], gen cost ($/h) per run
        starts            — list of (v_init_arr, ang_init_arr_deg) tuples
        n_converged       — number of NR runs that converged
        n_clusters        — number of distinct solutions found
    """
    rng = np.random.default_rng(seed)
    net_ref = pandapower_factory()
    n_bus = len(net_ref.bus)
    v_lo, v_hi = v_range
    a_lo, a_hi = angle_range

    starts = [
        (rng.uniform(v_lo, v_hi, n_bus).astype(float),
         rng.uniform(a_lo, a_hi, n_bus).astype(float))
        for _ in range(n_starts)
    ]

    circuit = circuit_factory()
    socp_result = solve_socp(circuit, mode=socp_mode,
                             gen_limits=gen_limits, gen_costs=gen_costs,
                             v_min=v_min, v_max=v_max)
    dc_result = solve_dc_opf(circuit, mode="opf",
                             gen_limits=gen_limits, gen_costs=gen_costs)

    nr_runs = [_run_nr_from_init(pandapower_factory, v, a) for v, a in starts]
    nr_obj_vals = [_gen_cost_from_nr(r, net_ref, gen_costs) for r in nr_runs]
    cluster_ids, clusters = _cluster_nr_solutions(nr_runs, tol_v=tol_v_cluster)

    return {
        "socp": socp_result,
        "dc_opf": dc_result,
        "nr_runs": nr_runs,
        "nr_cluster_ids": cluster_ids,
        "nr_clusters": clusters,
        "nr_obj_vals": nr_obj_vals,
        "starts": starts,
        "n_converged": sum(r["converged"] for r in nr_runs),
        "n_clusters": len(clusters),
    }


def print_multi_start_summary(results: Dict, grid_label: str = "") -> None:
    """Print a multi-start solution summary table to stdout."""
    label = f"Multi-start: {grid_label}" if grid_label else "Multi-start"
    n_s = len(results["nr_runs"])
    n_c = results["n_converged"]
    n_k = results["n_clusters"]
    has_cost = any(v is not None for v in results["nr_obj_vals"])

    print(f"\n{'='*60}")
    print(label)
    print(f"{'='*60}")
    print(f"{n_s} NR starts  |  {n_c} converged  |  {n_k} distinct solution(s)")

    cost_hdr = f"  {'cost($/h)':>10}" if has_cost else ""
    print(f"\n{'Run':>4}  {'Conv':>5}  {'Clust':>5}  {'min|V|':>7}  {'max|V|':>7}{cost_hdr}")
    print("-" * (38 + (13 if has_cost else 0)))
    for i, (r, cid, obj) in enumerate(
        zip(results["nr_runs"], results["nr_cluster_ids"], results["nr_obj_vals"])
    ):
        conv = "yes" if r["converged"] else "no"
        cid_s = str(cid) if cid is not None else "—"
        if r["converged"]:
            minv = f"{np.min(r['v_mag']):.4f}"
            maxv = f"{np.max(r['v_mag']):.4f}"
            obj_s = f"  {obj:>10.2f}" if (has_cost and obj is not None) else ""
        else:
            minv = maxv = "—"
            obj_s = ""
        print(f"{i+1:>4}  {conv:>5}  {cid_s:>5}  {minv:>7}  {maxv:>7}{obj_s}")

    if n_k > 0:
        cluster_counts: Dict[int, int] = {}
        for cid in results["nr_cluster_ids"]:
            if cid is not None:
                cluster_counts[cid] = cluster_counts.get(cid, 0) + 1

        print(f"\nDistinct NR solutions:")
        cost_hdr2 = f"  {'cost($/h)':>10}" if has_cost else ""
        print(f"{'Clust':>5}  {'Count':>5}  {'min|V|':>7}  {'max|V|':>7}{cost_hdr2}")
        print("-" * (30 + (13 if has_cost else 0)))
        for cid, rep in enumerate(results["nr_clusters"]):
            cnt = cluster_counts.get(cid, 0)
            minv = f"{np.min(rep['v_mag']):.4f}"
            maxv = f"{np.max(rep['v_mag']):.4f}"
            # cost of the representative run for this cluster
            rep_idx = next(i for i, c in enumerate(results["nr_cluster_ids"])
                           if c == cid)
            obj_r = results["nr_obj_vals"][rep_idx]
            obj_s2 = f"  {obj_r:>10.2f}" if (has_cost and obj_r is not None) else ""
            print(f"{cid:>5}  {cnt:>5}  {minv:>7}  {maxv:>7}{obj_s2}")

    print(f"\nConvex solvers (reference):")
    socp = results["socp"]
    dc = results["dc_opf"]
    s_obj = socp["details"].get("obj_val")
    d_obj = dc["details"].get("obj_val")
    s_obj_s = f"  cost={s_obj:.2f} $/h" if isinstance(s_obj, (int, float)) else ""
    d_obj_s = f"  cost={d_obj:.2f} $/h" if isinstance(d_obj, (int, float)) else ""
    if socp["converged"]:
        print(f"  SOCP  (converged)  min|V|={np.min(socp['v_mag']):.4f}  "
              f"max|V|={np.max(socp['v_mag']):.4f}{s_obj_s}")
    else:
        print("  SOCP  (FAILED)")
    s_dc = "converged" if dc["converged"] else "FAILED"
    print(f"  DC OPF ({s_dc}){d_obj_s}")


def multi_start_case14(n_starts: int = 20, seed: int = 42) -> Dict:
    """Multi-start comparison for IEEE 14-bus in pf mode."""
    return multi_start_comparison(
        make_case14_circuit, make_case14_pandapower,
        make_gen_limits(), make_gen_costs(),
        n_starts=n_starts,
        v_range=(1.0, 1.5), angle_range=(-60.0, 60.0),
        seed=seed, socp_mode="pf",
    )


def multi_start_wb5(n_starts: int = 20, seed: int = 42) -> Dict:
    """Multi-start comparison for WB5 in opf mode."""
    return multi_start_comparison(
        make_wb5_circuit,
        lambda: make_wb5_pandapower(vmax_pu=1.5, vmin_pu=0.5),
        make_wb5_gen_limits(), make_wb5_gen_costs(),
        n_starts=n_starts,
        v_range=(1.0, 1.5), angle_range=(-60.0, 60.0),
        seed=seed, socp_mode="opf", v_min=0.5, v_max=1.5,
    )


def multi_start_c22loop_asym(n_starts: int = 30, seed: int = 42) -> Dict:
    """Multi-start on Case22loop with asymmetric costs to reveal multiple local optima.

    Starting angles in [-30°, 30°] (matching the symmetric case); the broken
    symmetry from the cost split should push NR to distinct basins.
    """
    return multi_start_comparison(
        make_c22loop_circuit,
        lambda: make_c22loop_pandapower(vmax_pu=1.05, vmin_pu=0.95),
        make_c22loop_gen_limits(), make_c22loop_asym_gen_costs(),
        n_starts=n_starts,
        v_range=(0.95, 1.05), angle_range=(-30.0, 30.0),
        seed=seed, socp_mode="opf", v_min=0.95, v_max=1.05,
    )


def multi_start_c22loop(n_starts: int = 20, seed: int = 42) -> Dict:
    """Multi-start comparison for Case22loop in opf mode.

    Voltage range is kept near nominal [0.95, 1.05] pu (matching bus limits)
    and angles within [-30°, 30°] — the ring topology has moderate per-branch
    angle drops (~3-5°) so wide-angle starts all diverge.
    """
    return multi_start_comparison(
        make_c22loop_circuit,
        lambda: make_c22loop_pandapower(vmax_pu=1.05, vmin_pu=0.95),
        make_c22loop_gen_limits(), make_c22loop_gen_costs(),
        n_starts=n_starts,
        v_range=(0.95, 1.05), angle_range=(-30.0, 30.0),
        seed=seed, socp_mode="opf", v_min=0.95, v_max=1.05,
    )


# ── CLI ───────────────────────────────────────────────────────────────────

def main():
    print("Running IEEE 14-bus solver comparison...")
    r14 = compare_case14("case14_comparison.csv")
    print()
    print_summary(r14, "IEEE 14-bus")
    print()
    print("Wrote case14_comparison.csv\n")

    print("Running WB5 (Bukhsh 2013) solver comparison...")
    rwb5 = compare_wb5("wb5_comparison.csv")
    print()
    print_summary(rwb5, "WB5 — Bukhsh et al. 2013")
    print()
    print("Wrote wb5_comparison.csv\n")

    print("Running Case22loop (Bukhsh ring) solver comparison...")
    rc22 = compare_c22loop("c22loop_comparison.csv")
    print()
    print_summary(rc22, "Case22loop — uniform cost")
    print()
    print("Running Case22loop asymmetric-cost comparison...")
    rc22a = compare_c22loop_asym("c22loop_asym_comparison.csv")
    print()
    print_summary(rc22a, "Case22loop — asymmetric cost")
    print()
    print("Wrote c22loop_comparison.csv and c22loop_asym_comparison.csv\n")

    print("Running IEEE 14-bus multi-start (20 starts, high V/angle)...")
    ms14 = multi_start_case14(n_starts=20, seed=42)
    print_multi_start_summary(ms14, "IEEE 14-bus")

    print("\nRunning WB5 multi-start (20 starts, high V/angle)...")
    mswb5 = multi_start_wb5(n_starts=20, seed=42)
    print_multi_start_summary(mswb5, "WB5 — Bukhsh et al. 2013")

    print("\nRunning Case22loop multi-start (uniform cost)...")
    msc22 = multi_start_c22loop(n_starts=20, seed=42)
    print_multi_start_summary(msc22, "Case22loop — uniform cost")

    print("\nRunning Case22loop asymmetric-cost multi-start (30 starts)...")
    msc22a = multi_start_c22loop_asym(n_starts=30, seed=42)
    print_multi_start_summary(msc22a, "Case22loop — asymmetric cost")

    print("\nGenerating plots...")
    from plots import plot_all
    plot_all(
        compare_results={
            "wb5": rwb5,
            "c22loop": rc22,
            "c22loop_asym": rc22a,
        },
        multistart_results={
            "wb5": mswb5,
            "c22loop_asym": msc22a,
        },
    )
    print("Plots saved: fig_objectives.png, fig_multistart_costs.png, "
          "fig_voltages.png, fig_tightness.png, fig_ring_flows.png")


if __name__ == "__main__":
    main()
