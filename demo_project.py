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
from typing import Callable, Dict, List, Tuple

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
    bus_order: List[str] | None = None,
    branch_order: List[str] | None = None,
) -> Dict[str, dict]:
    """Run all four solvers on any grid and write a side-by-side CSV.

    Parameters
    ----------
    circuit_factory      : zero-arg callable returning a populated Circuit
    pandapower_factory   : zero-arg callable returning a populated pandapower net
                           (must use the same bus and branch *names* as the Circuit
                           so alignment by name works)
    gen_limits, gen_costs: same dicts passed to solve_socp / solve_dc_opf
    output_csv           : CSV path (three sections: summary, buses, branches)
    bus_order            : canonical bus name ordering for the CSV; if None,
                           uses the Circuit's Y-bus ordering
    branch_order         : canonical branch name ordering for the CSV; if None,
                           uses the Circuit ordering (lines first, then tx)

    Returns
    -------
    dict {solver_label: result_dict} for inspection.
    """
    results = {
        "socp_pf":  solve_socp(circuit_factory(), mode="pf",
                               gen_limits=gen_limits, gen_costs=gen_costs),
        "dc_opf":   solve_dc_opf(circuit_factory(), mode="opf",
                                 gen_limits=gen_limits, gen_costs=gen_costs),
        "pp_acpf":  solve_pandapower(pandapower_factory(), mode="pf"),
        "pp_dcopf": solve_pandapower(pandapower_factory(), mode="opf",
                                     gen_costs=gen_costs),
    }

    # Source orderings each solver returns its results in
    _circ = circuit_factory()
    circuit_bus_order = list(_circ.calc_ybus().index)
    circuit_branch_order = _circuit_branch_order(_circ)
    _net = pandapower_factory()
    pp_bus_order = _net.bus["name"].tolist()
    pp_branch_order = _net.line["name"].tolist()

    src = {
        "socp_pf":  (circuit_bus_order, circuit_branch_order),
        "dc_opf":   (circuit_bus_order, circuit_branch_order),
        "pp_acpf":  (pp_bus_order,      pp_branch_order),
        "pp_dcopf": (pp_bus_order,      pp_branch_order),
    }

    bus_target = bus_order if bus_order is not None else circuit_bus_order
    branch_target = branch_order if branch_order is not None else circuit_branch_order

    with open(output_csv, "w", newline="") as f:
        w = csv.writer(f)

        # ── Section 1: summary ─────────────────────────────────────────────
        w.writerow(["solver", "mode", "converged", "solve_time_s", "obj_val"])
        for label, mode in _LABELS_MODES:
            r = results[label]
            t = r["details"].get("solve_time_s", None)
            obj = r["details"].get("obj_val", None)
            w.writerow([label, mode, r["converged"],
                        _format_num(t), _format_num(obj)])
        w.writerow([])

        # ── Section 2: bus voltages ─────────────────────────────────────────
        header = ["bus_name"]
        header += [f"{lbl}_vmag" for lbl, _ in _LABELS_MODES]
        header += [f"{lbl}_vang_deg" for lbl, _ in _LABELS_MODES]
        w.writerow(header)

        aligned_vmag = {lbl: _align_by_name(results[lbl]["v_mag"],
                                             src[lbl][0], bus_target)
                        for lbl, _ in _LABELS_MODES}
        aligned_vang = {lbl: _align_by_name(results[lbl]["v_ang_deg"],
                                             src[lbl][0], bus_target)
                        for lbl, _ in _LABELS_MODES}
        for i, name in enumerate(bus_target):
            row = [name]
            for lbl, _ in _LABELS_MODES:
                row.append(_format_num(aligned_vmag[lbl][i]))
            for lbl, _ in _LABELS_MODES:
                row.append(_format_num(aligned_vang[lbl][i]))
            w.writerow(row)
        w.writerow([])

        # ── Section 3: branch flows (from-end pu) ──────────────────────────
        header = ["branch_name"]
        header += [f"{lbl}_p_from_pu" for lbl, _ in _LABELS_MODES]
        header += [f"{lbl}_q_from_pu" for lbl, _ in _LABELS_MODES]
        w.writerow(header)

        aligned_p = {lbl: _align_by_name(results[lbl]["p_fr"],
                                          src[lbl][1], branch_target)
                     for lbl, _ in _LABELS_MODES}
        aligned_q = {lbl: _align_by_name(results[lbl]["q_fr"],
                                          src[lbl][1], branch_target)
                     for lbl, _ in _LABELS_MODES}
        for i, name in enumerate(branch_target):
            row = [name]
            for lbl, _ in _LABELS_MODES:
                row.append(_format_num(aligned_p[lbl][i]))
            for lbl, _ in _LABELS_MODES:
                row.append(_format_num(aligned_q[lbl][i]))
            w.writerow(row)
        w.writerow([])

        # ── Section 4: SOCP relaxation tightness per branch ────────────────
        # τ = |W_ij|² / (W_ii W_jj) — 1.0 means SOC is active (rank-1 OK at
        # this branch); < 1.0 means the lifted W is non-physical there.
        # in_loop = "yes" if this branch closes a fundamental cycle in the
        # BFS spanning tree from the slack; loop_residual_deg is the angle
        # mismatch around that cycle (only meaningful for non-tree branches).
        tight = branch_tightness(circuit_factory(), results["socp_pf"])
        loops = loop_residuals(circuit_factory(), results["socp_pf"])
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

    # Stash the tightness summary on the returned dict so callers can print it
    results["_socp_tightness"] = dict(
        max_gap=tight["worst_gap"],
        worst_branch=tight["worst_branch"],
        max_loop_residual_deg=loops["max_abs_deg"],
    )
    return results


def print_summary(results: Dict[str, dict], grid_label: str = "") -> None:
    """Pretty-print the four-solver summary table to stdout."""
    title = f"Comparison: {grid_label}" if grid_label else "Comparison"
    print(title)
    print(f"{'solver':<10} {'mode':<5} {'converged':<10} "
          f"{'time (s)':>10} {'obj':>12}")
    print("-" * 55)
    for label, mode in _LABELS_MODES:
        r = results[label]
        t = r["details"].get("solve_time_s", float("nan"))
        obj = r["details"].get("obj_val", "")
        obj_str = f"{obj:>12.4f}" if isinstance(obj, (int, float)) else " " * 12
        t_str = f"{t:>10.4f}" if isinstance(t, (int, float)) else " " * 10
        print(f"{label:<10} {mode:<5} {str(r['converged']):<10} "
              f"{t_str} {obj_str}")

    tight = results.get("_socp_tightness")
    if tight is not None:
        print()
        print("SOCP relaxation diagnostics:")
        print(f"  max(1 − τ)   = {tight['max_gap']:.3e}   "
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


# ── CLI ───────────────────────────────────────────────────────────────────

def main():
    print("Running IEEE 14-bus solver comparison...")
    results = compare_case14("case14_comparison.csv")
    print()
    print_summary(results, "IEEE 14-bus")
    print()
    print("Wrote case14_comparison.csv")


if __name__ == "__main__":
    main()
