"""
Visualization module for the OPF comparison framework.

All functions take pre-computed result dicts from demo_project.py and produce
publication-quality matplotlib figures saved as PNG files.

Public API
----------
plot_objective_comparison(results_by_case, save_path)
plot_multi_start_costs(ms_results_by_case, save_path)
plot_voltage_profiles(ms_results_by_case, save_path)
plot_socp_tightness(results_by_case, save_path)
plot_ring_flows(ms_c22loop_asym, save_path)
plot_all(compare_results, multistart_results, prefix)
"""
from __future__ import annotations

import math
from typing import Dict, Optional

import matplotlib
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

matplotlib.rcParams.update({
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "legend.fontsize": 9,
    "figure.dpi": 150,
})

_CLUSTER_COLORS = ["#2196F3", "#FF9800", "#4CAF50", "#E91E63", "#9C27B0"]
_DIVERGED_COLOR = "#BDBDBD"


# ── Figure 1: Solver objective comparison ────────────────────────────────────

def plot_objective_comparison(
    results_by_case: Dict[str, dict],
    save_path: str = "fig_objectives.png",
    show: bool = False,
) -> plt.Figure:
    """Grouped bar chart of objective values across solvers for each case.

    Parameters
    ----------
    results_by_case : dict mapping case label → compare_solvers() result dict
                      Include only OPF cases (wb5, c22loop, c22loop_asym).
                      case14 uses pf mode and has no comparable OPF cost.
    """
    solver_display = {
        "socp_opf": ("SOCP", "#1565C0"),
        "dc_opf":   ("DC OPF", "#43A047"),
        "pp_acopf": ("AC OPF\n(pp.runopp)", "#E53935"),
        "pp_acpf":  ("NR (flat\nstart)", "#FB8C00"),
    }

    case_labels = list(results_by_case.keys())
    n_cases = len(case_labels)

    fig, axes = plt.subplots(1, n_cases, figsize=(4.2 * n_cases, 5), sharey=False)
    if n_cases == 1:
        axes = [axes]

    for ax, case_lbl in zip(axes, case_labels):
        res = results_by_case[case_lbl]
        labels_modes = res.get("_labels_modes", [])
        present = {lbl for lbl, _ in labels_modes}

        # Build ordered list of solvers that exist in this result
        solvers = [k for k in solver_display if k in present]
        # Always include NR flat-start from compare result if available
        if "pp_acpf" in present and "pp_acpf" not in solvers:
            solvers.append("pp_acpf")

        objs = []
        names = []
        colors = []
        for s in solvers:
            obj = res.get(s, {}).get("details", {}).get("obj_val")
            if obj is None or (isinstance(obj, float) and math.isnan(obj)):
                continue
            objs.append(obj)
            disp, col = solver_display[s]
            names.append(disp)
            colors.append(col)

        if not objs:
            ax.set_title(case_lbl)
            ax.text(0.5, 0.5, "no OPF data", ha="center", va="center",
                    transform=ax.transAxes)
            continue

        x = np.arange(len(objs))
        bars = ax.bar(x, objs, color=colors, width=0.6, edgecolor="white",
                      linewidth=0.8)

        # Duality gap annotation: compare SOCP to AC OPF if both present
        socp_obj = res.get("socp_opf", {}).get("details", {}).get("obj_val")
        acopf_obj = res.get("pp_acopf", {}).get("details", {}).get("obj_val")
        if (socp_obj is not None and acopf_obj is not None
                and acopf_obj > 0 and socp_obj is not None):
            gap_pct = (acopf_obj - socp_obj) / acopf_obj * 100
            if abs(gap_pct) > 0.5:
                socp_idx = solvers.index("socp_opf")
                ax.annotate(
                    f"gap\n{gap_pct:.0f}%",
                    xy=(socp_idx, socp_obj),
                    xytext=(socp_idx, socp_obj + (acopf_obj - socp_obj) * 0.4),
                    ha="center", fontsize=8, color="#1565C0",
                    arrowprops=dict(arrowstyle="->", color="#1565C0", lw=1.2),
                )

        ax.set_xticks(x)
        ax.set_xticklabels(names, fontsize=8)
        ax.set_ylabel("Objective ($/h)")
        ax.set_title(case_lbl, fontweight="bold")
        ax.set_ylim(bottom=0)
        ax.yaxis.grid(True, linestyle="--", alpha=0.5)
        ax.set_axisbelow(True)

        for bar, val in zip(bars, objs):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(objs) * 0.01,
                    f"{val:,.0f}", ha="center", va="bottom", fontsize=8)

    fig.suptitle("Solver Objective Comparison", fontsize=13, fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight")
    if show:
        plt.show()
    return fig


# ── Figure 2: Multi-start cost distribution ───────────────────────────────────

def plot_multi_start_costs(
    ms_results_by_case: Dict[str, dict],
    compare_results_by_case: Optional[Dict[str, dict]] = None,
    save_path: str = "fig_multistart_costs.png",
    show: bool = False,
) -> plt.Figure:
    """Strip/dot plot of per-run NR costs with SOCP and AC OPF reference lines.

    Parameters
    ----------
    ms_results_by_case      : dict mapping case label → multi_start_comparison() dict
    compare_results_by_case : optional dict mapping same case labels →
                              compare_solvers() dicts (for pp_acopf reference)
    """
    cases = list(ms_results_by_case.keys())
    n = len(cases)
    fig, axes = plt.subplots(1, n, figsize=(4.5 * n, 5), sharey=False)
    if n == 1:
        axes = [axes]

    for ax, case_lbl in zip(axes, cases):
        ms = ms_results_by_case[case_lbl]
        obj_vals = ms["nr_obj_vals"]
        cluster_ids = ms["nr_cluster_ids"]
        n_runs = len(obj_vals)

        # Scatter converged runs first so y-limits are set before diverged markers
        valid_objs = [o for o in obj_vals if o is not None]
        y_base = min(valid_objs) * 0.97 if valid_objs else 0.0

        for i, (obj, cid) in enumerate(zip(obj_vals, cluster_ids)):
            if obj is None:
                ax.scatter(i, y_base, color=_DIVERGED_COLOR, marker="x",
                           s=55, zorder=3, linewidths=1.5)
                continue
            col = _CLUSTER_COLORS[cid % len(_CLUSTER_COLORS)] if cid is not None else _DIVERGED_COLOR
            ax.scatter(i, obj, color=col, s=55, zorder=3, edgecolors="white", linewidths=0.5)

        # Reference lines — collect Line2D handles
        ref_handles = []
        socp_obj = ms["socp"].get("details", {}).get("obj_val")
        dc_obj = ms["dc_opf"].get("details", {}).get("obj_val")
        acopf_obj = None
        if compare_results_by_case and case_lbl in compare_results_by_case:
            acopf_obj = (compare_results_by_case[case_lbl]
                         .get("pp_acopf", {}).get("details", {}).get("obj_val"))

        if socp_obj is not None:
            (line,) = ax.plot([], [], color="#1565C0", linestyle="--", linewidth=1.5,
                              label=f"SOCP lb {socp_obj:,.0f} $/h")
            ax.axhline(socp_obj, color="#1565C0", linestyle="--", linewidth=1.5)
            ref_handles.append(line)
        if dc_obj is not None:
            (line,) = ax.plot([], [], color="#43A047", linestyle=":", linewidth=1.5,
                              label=f"DC OPF lb {dc_obj:,.0f} $/h")
            ax.axhline(dc_obj, color="#43A047", linestyle=":", linewidth=1.5)
            ref_handles.append(line)
        if acopf_obj is not None:
            (line,) = ax.plot([], [], color="#E53935", linestyle="-", linewidth=1.5,
                              label=f"AC OPF {acopf_obj:,.0f} $/h")
            ax.axhline(acopf_obj, color="#E53935", linestyle="-", linewidth=1.5)
            ref_handles.append(line)

        # Cluster patches
        cluster_patch = [mpatches.Patch(color=_DIVERGED_COLOR, label="diverged")]
        for cid, _rep in enumerate(ms["nr_clusters"]):
            obj_rep = ms["nr_obj_vals"][
                next(ii for ii, c in enumerate(ms["nr_cluster_ids"]) if c == cid)
            ]
            col = _CLUSTER_COLORS[cid % len(_CLUSTER_COLORS)]
            n_in = sum(1 for c in ms["nr_cluster_ids"] if c == cid)
            cluster_patch.append(
                mpatches.Patch(color=col,
                               label=f"Cluster {cid} ({n_in} runs, {obj_rep:,.0f} $/h)")
            )

        ax.set_xlabel("NR run index")
        ax.set_ylabel("Generation cost ($/h)")
        ax.set_title(f"{case_lbl}\nmulti-start cost distribution", fontweight="bold")
        ax.set_xlim(-0.5, n_runs - 0.5)
        ax.yaxis.grid(True, linestyle="--", alpha=0.4)
        ax.set_axisbelow(True)
        ax.legend(handles=ref_handles + cluster_patch, fontsize=8)

    fig.suptitle("Multi-Start NR: Cost per Run", fontsize=13, fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight")
    if show:
        plt.show()
    return fig


# ── Figure 3: Voltage magnitude profiles ─────────────────────────────────────

def plot_voltage_profiles(
    ms_results_by_case: Dict[str, dict],
    save_path: str = "fig_voltages.png",
    show: bool = False,
) -> plt.Figure:
    """Grouped bar chart of voltage magnitudes per bus for each distinct NR cluster + SOCP.

    Parameters
    ----------
    ms_results_by_case : dict mapping case label → multi_start_comparison() dict
    """
    cases = list(ms_results_by_case.keys())
    n = len(cases)
    fig, axes = plt.subplots(n, 1, figsize=(12, 4.5 * n), squeeze=False)

    for row, case_lbl in enumerate(cases):
        ax = axes[row][0]
        ms = ms_results_by_case[case_lbl]
        clusters = ms["nr_clusters"]
        socp = ms["socp"]

        n_bus = len(socp["v_mag"])
        x = np.arange(n_bus)

        # Determine bar group width
        n_series = 1 + len(clusters)  # SOCP + each NR cluster
        width = 0.8 / n_series

        # SOCP reference
        ax.bar(x - (n_series - 1) / 2 * width + 0 * width,
               socp["v_mag"], width=width, label="SOCP", color="#1565C0",
               edgecolor="white", linewidth=0.5)

        for cid, rep in enumerate(clusters):
            col = _CLUSTER_COLORS[cid % len(_CLUSTER_COLORS)]
            n_in = sum(1 for c in ms["nr_cluster_ids"] if c == cid)
            offset = (cid + 1) * width
            ax.bar(x - (n_series - 1) / 2 * width + offset,
                   rep["v_mag"], width=width,
                   label=f"NR cluster {cid} ({n_in} runs)",
                   color=col, edgecolor="white", linewidth=0.5)

        ax.set_xticks(x)
        ax.set_xticklabels([f"B{i+1}" for i in range(n_bus)], fontsize=8, rotation=45)
        ax.set_ylabel("|V| (pu)")
        ax.set_title(f"{case_lbl} — voltage magnitudes by operating point", fontweight="bold")
        ax.legend(fontsize=8)
        ax.set_ylim(bottom=0.8)
        ax.yaxis.grid(True, linestyle="--", alpha=0.4)
        ax.set_axisbelow(True)

    fig.suptitle("Voltage Profiles Across Distinct NR Solutions", fontsize=13,
                 fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight")
    if show:
        plt.show()
    return fig


# ── Figure 4: SOCP branch tightness ──────────────────────────────────────────

def plot_socp_tightness(
    results_by_case: Dict[str, dict],
    save_path: str = "fig_tightness.png",
    show: bool = False,
) -> plt.Figure:
    """Horizontal bar chart of per-branch τ values with loop residual annotations.

    Parameters
    ----------
    results_by_case : dict mapping case label → compare_solvers() result dict
                      Should include cases with interesting tightness contrast
                      (e.g. WB5 with gap vs. c22loop exact).
    """
    cases = list(results_by_case.keys())
    n = len(cases)
    max_branches = max(
        (len(v.get("_socp_tightness", {}).get("branch_names") or [])
         for v in results_by_case.values()),
        default=20,
    )
    fig_h = max(5, 0.32 * max_branches)
    fig, axes = plt.subplots(1, n, figsize=(6.5 * n, fig_h), sharey=False)
    if n == 1:
        axes = [axes]

    for ax, case_lbl in zip(axes, cases):
        res = results_by_case[case_lbl]
        tight = res.get("_socp_tightness", {})
        max_loop = tight.get("max_loop_residual_deg", 0.0)

        tau_names = tight.get("branch_names")
        tau_vals = tight.get("tau")
        loop_res_lookup = tight.get("loop_residuals_deg", {})

        if tau_names is None or tau_vals is None:
            ax.set_title(f"{case_lbl}\n(no tightness data)")
            continue

        n_br = len(tau_names)
        y = np.arange(n_br)
        gaps = 1.0 - np.array(tau_vals)

        bar_colors = ["#E53935" if g > 1e-4 else "#43A047" for g in gaps]
        ax.barh(y, tau_vals, color=bar_colors, edgecolor="white", linewidth=0.5)

        ax.axvline(1.0, color="#333333", linestyle="--", linewidth=1, label="τ = 1")
        ax.set_xlim(max(0, min(tau_vals) - 0.05), 1.05)
        ax.set_yticks(y)
        ax.set_yticklabels(tau_names, fontsize=8)
        ax.set_xlabel("Branch tightness τ = |W_ij|² / (W_ii · W_jj)")

        # Annotate non-tree branches with loop residual
        for j, name in enumerate(tau_names):
            delta = loop_res_lookup.get(name)
            if delta is not None:
                ax.text(1.02, j, f"Δ={delta:.2f}°", va="center", fontsize=7.5,
                        color="#E65100")

        exact = abs(max_loop) < 0.1
        title_suffix = "SOCP exact (Δ≈0°)" if exact else f"SOCP inexact (max Δ={max_loop:.2f}°)"
        ax.set_title(f"{case_lbl}\n{title_suffix}", fontweight="bold")
        ax.xaxis.grid(True, linestyle="--", alpha=0.4)
        ax.set_axisbelow(True)

        tight_patch = mpatches.Patch(color="#43A047", label="tight (τ≈1, no gap)")
        gap_patch = mpatches.Patch(color="#E53935", label="gap (τ<1)")
        ax.legend(handles=[tight_patch, gap_patch], fontsize=8)

    fig.suptitle("SOCP Branch Tightness τ per Branch", fontsize=13,
                 fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight")
    if show:
        plt.show()
    return fig


# ── Figure 5: Ring power flow diagram ────────────────────────────────────────

def plot_ring_flows(
    ms_c22loop_asym: dict,
    compare_c22loop_asym: Optional[dict] = None,
    save_path: str = "fig_ring_flows.png",
    show: bool = False,
) -> plt.Figure:
    """Circular network diagram showing two operating regimes for case22loop_asym.

    Left panel: balanced operating point (NR flat start = first cluster).
    Right panel: globally optimal dispatch (SOCP / pp_acopf = second cluster or SOCP).
    Node color: cheap arc (buses 1–11) = blue, expensive arc (buses 13–21) = orange.
    Arrow width proportional to |active power flow|.
    """
    N = 22

    def _bus_positions(n):
        angles_rad = [2 * np.pi * i / n - np.pi / 2 for i in range(n)]
        return [(np.cos(a), np.sin(a)) for a in angles_rad]

    pos = _bus_positions(N)

    # Determine which cluster is balanced vs optimal
    clusters = ms_c22loop_asym["nr_clusters"]
    socp = ms_c22loop_asym["socp"]

    # The balanced cluster has higher cost; optimal has lower cost
    nr_obj_vals = ms_c22loop_asym["nr_obj_vals"]
    valid_objs = [(v, c) for v, c in
                  zip(nr_obj_vals, ms_c22loop_asym["nr_cluster_ids"])
                  if v is not None and c is not None]

    # Mean cost per cluster
    cluster_costs = {}
    for obj, cid in valid_objs:
        cluster_costs.setdefault(cid, []).append(obj)
    cluster_mean = {cid: np.mean(vals) for cid, vals in cluster_costs.items()}

    if len(clusters) >= 2:
        sorted_cids = sorted(cluster_mean, key=cluster_mean.get)
        cheap_cluster = clusters[sorted_cids[0]]   # lower cost = optimal
        expensive_cluster = clusters[sorted_cids[1]]  # higher cost = balanced
    elif len(clusters) == 1:
        cheap_cluster = clusters[0]
        expensive_cluster = clusters[0]
    else:
        cheap_cluster = socp
        expensive_cluster = socp

    panels = [
        (expensive_cluster, "Balanced operating point\n(NR flat start)"),
        (socp, "Globally optimal dispatch\n(SOCP / AC OPF)"),
    ]

    fig, axes = plt.subplots(1, 2, figsize=(13, 6.5))

    for ax, (result, title) in zip(axes, panels):
        p_fr = result["p_fr"]  # shape (n_branches,); branches are 1→2, 2→3, …, 22→1

        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title(title, fontweight="bold", fontsize=11)

        max_p = max(np.max(np.abs(p_fr)), 1e-6)

        for k in range(N):
            fr_bus = k          # 0-indexed; branch k connects bus k → bus (k+1)%N
            to_bus = (k + 1) % N
            x0, y0 = pos[fr_bus]
            x1, y1 = pos[to_bus]
            flow = p_fr[k] if k < len(p_fr) else 0.0

            lw = 0.5 + 5.5 * abs(flow) / max_p
            col = "#1565C0" if flow >= 0 else "#E53935"

            # Draw line
            ax.plot([x0, x1], [y0, y1], color=col, linewidth=lw,
                    solid_capstyle="round", alpha=0.85)

            # Arrow at midpoint
            mid_x = (x0 + x1) / 2
            mid_y = (y0 + y1) / 2
            dx = (x1 - x0) * 0.001 * np.sign(flow) if abs(flow) > max_p * 0.02 else 0
            dy = (y1 - y0) * 0.001 * np.sign(flow) if abs(flow) > max_p * 0.02 else 0
            if dx != 0 or dy != 0:
                ax.annotate("", xy=(mid_x + dx, mid_y + dy),
                            xytext=(mid_x - dx, mid_y - dy),
                            arrowprops=dict(arrowstyle="-|>", color=col,
                                            lw=0.8, mutation_scale=10))

        for i, (x, y) in enumerate(pos):
            bus_num = i + 1  # 1-indexed
            is_gen = (bus_num % 2 == 1)  # odd buses host generators
            is_cheap = (1 <= bus_num <= 11)
            node_col = "#1565C0" if is_cheap else "#FB8C00"
            node_alpha = 1.0 if is_gen else 0.5
            radius = 0.08 if is_gen else 0.055
            circle = plt.Circle((x, y), radius, color=node_col, alpha=node_alpha,
                                 zorder=5)
            ax.add_patch(circle)
            ax.text(x, y, str(bus_num), ha="center", va="center",
                    fontsize=6.5, color="white", fontweight="bold", zorder=6)

        # Voltage magnitude ring annotation (faint grey dashed circle at |V|)
        v_mag = result["v_mag"]
        if len(v_mag) == N:
            for i, (x, y) in enumerate(pos):
                v = v_mag[i]
                scale = 1.12
                vx = x * scale * v
                vy = y * scale * v
                ax.plot(vx, vy, ".", color="#9E9E9E", markersize=3, zorder=4)

        # Legend
        cheap_patch = mpatches.Patch(color="#1565C0", label="Cheap arc (buses 1–11, $1/MWh)")
        exp_patch = mpatches.Patch(color="#FB8C00", label="Expensive arc (buses 13–21, $4/MWh)")
        fwd_patch = mpatches.Patch(color="#1565C0", alpha=0.6, label="P > 0 (clockwise)")
        rev_patch = mpatches.Patch(color="#E53935", alpha=0.6, label="P < 0 (counterclockwise)")
        ax.legend(handles=[cheap_patch, exp_patch, fwd_patch, rev_patch],
                  loc="lower center", fontsize=7.5,
                  bbox_to_anchor=(0.5, -0.06), ncol=2)

        obj = result["details"].get("obj_val")
        obj_str = f"{obj:,.0f} $/h" if obj is not None else "N/A"
        ax.text(0, 0, f"{obj_str}", ha="center", va="center", fontsize=10,
                color="#333333", fontweight="bold")

    fig.suptitle("Case22loop Asymmetric Cost — Ring Power Flow Patterns",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight")
    if show:
        plt.show()
    return fig


# ── Convenience wrapper ───────────────────────────────────────────────────────

def plot_all(
    compare_results: Dict[str, dict],
    multistart_results: Dict[str, dict],
    prefix: str = "fig_",
    show: bool = False,
) -> Dict[str, plt.Figure]:
    """Run all 5 plot functions and save figures.

    Parameters
    ----------
    compare_results    : {"case14": r14, "wb5": rwb5, "c22loop": rc22, "c22loop_asym": rc22a}
    multistart_results : {"wb5": mswb5, "c22loop_asym": msc22a}
    prefix             : filename prefix for saved PNGs
    """
    figs = {}

    # Figure 1 — objective comparison (OPF cases only)
    opf_cases = {k: v for k, v in compare_results.items()
                 if k != "case14"}
    if opf_cases:
        print(f"  Saving {prefix}objectives.png ...")
        figs["objectives"] = plot_objective_comparison(
            opf_cases, save_path=f"{prefix}objectives.png", show=show
        )

    # Figure 2 — multi-start cost distribution
    if multistart_results:
        print(f"  Saving {prefix}multistart_costs.png ...")
        figs["multistart_costs"] = plot_multi_start_costs(
            multistart_results,
            compare_results_by_case=compare_results,
            save_path=f"{prefix}multistart_costs.png",
            show=show,
        )

    # Figure 3 — voltage profiles
    if multistart_results:
        print(f"  Saving {prefix}voltages.png ...")
        figs["voltages"] = plot_voltage_profiles(
            multistart_results,
            save_path=f"{prefix}voltages.png",
            show=show,
        )

    # Figure 4 — SOCP tightness (WB5 vs c22loop for contrast)
    tightness_cases = {k: v for k, v in compare_results.items()
                       if k in ("wb5", "c22loop")}
    if tightness_cases:
        print(f"  Saving {prefix}tightness.png ...")
        figs["tightness"] = plot_socp_tightness(
            tightness_cases,
            save_path=f"{prefix}tightness.png",
            show=show,
        )

    # Figure 5 — ring flow diagram
    if "c22loop_asym" in multistart_results:
        print(f"  Saving {prefix}ring_flows.png ...")
        figs["ring_flows"] = plot_ring_flows(
            multistart_results["c22loop_asym"],
            compare_c22loop_asym=compare_results.get("c22loop_asym"),
            save_path=f"{prefix}ring_flows.png",
            show=show,
        )

    plt.close("all")
    return figs
