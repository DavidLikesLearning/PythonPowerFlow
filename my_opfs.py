"""
my_opfs.py — Interactive solver comparison tool for PythonPowerFlow.

Run with:  python my_opfs.py

Prompts the user to choose solvers, a grid, optional custom generator costs,
metrics to display, and whether to save outputs.  All solver orchestration is
delegated to compare_solvers() in demo_project.py; this file only handles
prompting, display filtering, and plot saving.
"""
from __future__ import annotations

import csv
import os
import sys
import tempfile
from typing import Dict, List, Optional, Set, Tuple


# ── Prompt helpers ────────────────────────────────────────────────────────────

def _divider(char: str = "─", width: int = 60) -> str:
    return char * width


def prompt_choice(prompt: str, valid: List[str]) -> str:
    """Prompt until the user enters one of the valid strings."""
    while True:
        raw = input(prompt).strip()
        if raw in valid:
            return raw
        print(f"  Invalid input '{raw}'. Please enter one of: {', '.join(valid)}")


def prompt_multi_choice(prompt: str, n_items: int, min_select: int = 0) -> List[int]:
    """Prompt for comma-separated integers 1..n_items.  Returns 0-indexed list."""
    valid_set = set(range(1, n_items + 1))
    while True:
        raw = input(prompt).strip()
        if raw == "" and min_select == 0:
            return []
        try:
            nums = [int(x.strip()) for x in raw.split(",") if x.strip()]
        except ValueError:
            print("  Enter numbers separated by commas (e.g. 1,3).")
            continue
        if any(n not in valid_set for n in nums):
            print(f"  Each number must be between 1 and {n_items}.")
            continue
        if len(set(nums)) < min_select:
            print(f"  Select at least {min_select} option(s).")
            continue
        return [n - 1 for n in dict.fromkeys(nums)]  # deduplicate, preserve order


def prompt_yes_no(prompt: str, default: bool = True) -> bool:
    """Prompt for Y/n.  Returns bool."""
    hint = "[Y/n]" if default else "[y/N]"
    while True:
        raw = input(f"{prompt} {hint}: ").strip().lower()
        if raw == "":
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  Enter 'y' or 'n'.")


def prompt_filepath(prompt: str, must_exist: bool = False, default: str = "") -> str:
    """Prompt for a file path, optionally validating existence."""
    hint = f" [{default}]" if default else ""
    while True:
        raw = input(f"{prompt}{hint}: ").strip()
        if raw == "" and default:
            raw = default
        if not raw:
            print("  Path cannot be empty.")
            continue
        if must_exist and not os.path.isfile(raw):
            print(f"  File not found: {raw}")
            continue
        return raw


def prompt_directory(prompt: str, default: str = ".") -> str:
    """Prompt for a directory path, offering to create it if it doesn't exist."""
    hint = f" [{default}]"
    while True:
        raw = input(f"{prompt}{hint}: ").strip() or default
        if os.path.isdir(raw):
            return raw
        yn = input(f"  Directory '{raw}' does not exist. Create it? [Y/n]: ").strip().lower()
        if yn in ("", "y", "yes"):
            os.makedirs(raw, exist_ok=True)
            print(f"  Created: {raw}")
            return raw
        print("  Enter a valid directory path.")


# ── Step 1 — Grid selection ───────────────────────────────────────────────────

# SOC mode defaults per grid number — needed before imports to annotate Step 2
_GRID_SOCP_MODE_DEFAULT = {1: "pf", 2: "opf", 3: "opf", 4: "opf"}


def prompt_grid() -> int:
    """Returns 1-based grid choice."""
    print(f"\n{_divider()}")
    print("[Step 1] Grid")
    print("  1. IEEE 14-bus")
    print("  2. WB5  (Bukhsh 2013 — non-convex bottleneck, SOCP duality gap)")
    print("  3. Case22loop — uniform costs ($2/MWh, exact SOCP)")
    print("  4. Case22loop — asymmetric costs ($1/$4 split, multiple local optima)")
    return int(prompt_choice("Enter choice [1-4]: ", ["1", "2", "3", "4"]))


# ── Step 2 — Solver selection ─────────────────────────────────────────────────

def prompt_solvers(grid_num: int) -> List[int]:
    """Returns 0-indexed list of selected solvers (empty = all selected)."""
    socp_mode = _GRID_SOCP_MODE_DEFAULT[grid_num]
    socp_mode_label = "OPF" if socp_mode == "opf" else "PF"
    print(f"\n{_divider()}")
    print("[Step 2] Solvers to run  (comma-separated, or Enter for all)")
    print(f"  1. Circuits NR    (Newton-Raphson AC power flow)")
    print(f"  2. Project DC OPF (cvxpy linear DC OPF)")
    print(f"  3. Project SOCP   (SOCP relaxation — {socp_mode_label} mode for this grid)")
    print(f"  4. Panda DC OPF   (linear DC OPF)")
    print(f"  5. Panda AC OPF   (interior-point AC OPF — slow)")
    idxs = prompt_multi_choice("Enter numbers (e.g. 1,3 — or Enter for all): ", 5)
    return idxs if idxs else list(range(5))


# ── Grid registry (built after imports) ──────────────────────────────────────

def _build_grid_registry(imports: dict) -> Dict[int, dict]:
    """Constructs the grid config lookup table after heavy modules are imported."""
    m = imports  # alias
    return {
        1: {
            "label": "IEEE 14-bus",
            "grid_key": "case14",
            "circuit_factory": m["make_case14_circuit"],
            "pandapower_factory": m["make_case14_pandapower"],
            "gen_limits_factory": m["make_gen_limits"],
            "gen_costs_factory": m["make_gen_costs"],
            "gen_data": m["GEN_DATA"],
            "v_min": 0.5, "v_max": 1.5,
            "socp_mode_default": "pf",
            "csv_default": "case14_comparison.csv",
        },
        2: {
            "label": "WB5",
            "grid_key": "wb5",
            "circuit_factory": m["make_wb5_circuit"],
            "pandapower_factory": lambda: m["make_wb5_pandapower"](vmax_pu=1.5, vmin_pu=0.5),
            "gen_limits_factory": m["make_wb5_gen_limits"],
            "gen_costs_factory": m["make_wb5_gen_costs"],
            "gen_data": m["GEN_DATA_WB5"],
            "v_min": 0.5, "v_max": 1.5,
            "socp_mode_default": "opf",
            "csv_default": "wb5_comparison.csv",
        },
        3: {
            "label": "Case22loop (uniform)",
            "grid_key": "c22loop",
            "circuit_factory": m["make_c22loop_circuit"],
            "pandapower_factory": lambda: m["make_c22loop_pandapower"](1.05, 0.95),
            "gen_limits_factory": m["make_c22loop_gen_limits"],
            "gen_costs_factory": m["make_c22loop_gen_costs"],
            "gen_data": m["GEN_DATA_C22"],
            "v_min": 0.95, "v_max": 1.05,
            "socp_mode_default": "opf",
            "csv_default": "c22loop_comparison.csv",
        },
        4: {
            "label": "Case22loop (asymmetric)",
            "grid_key": "c22loop_asym",
            "circuit_factory": m["make_c22loop_circuit"],
            "pandapower_factory": lambda: m["make_c22loop_pandapower"](1.05, 0.95),
            "gen_limits_factory": m["make_c22loop_gen_limits"],
            "gen_costs_factory": m["make_c22loop_asym_gen_costs"],
            "gen_data": m["GEN_DATA_C22"],
            "v_min": 0.95, "v_max": 1.05,
            "socp_mode_default": "opf",
            "csv_default": "c22loop_asym_comparison.csv",
        },
    }


# ── Step 4 — Generator costs ──────────────────────────────────────────────────

def parse_custom_costs_list(raw: str, gen_names: List[str]) -> Dict[str, float]:
    """Parse a comma-separated string of floats and map them to gen_names."""
    parts = [x.strip() for x in raw.split(",") if x.strip()]
    if len(parts) != len(gen_names):
        raise ValueError(
            f"Expected {len(gen_names)} values, got {len(parts)}. "
            f"Generators: {', '.join(gen_names)}"
        )
    return {name: float(v) for name, v in zip(gen_names, parts)}


def parse_custom_costs_csv(filepath: str, gen_names: List[str]) -> Dict[str, float]:
    """Parse a CSV into a gen_costs dict.

    Accepts two formats:
      - Two-column: gen_name,cost  (header optional)
      - One-column: numeric costs in generator order (no header)
    Auto-detects format by checking whether the first data cell is a float.
    """
    with open(filepath, newline="") as f:
        rows = [r for r in csv.reader(f) if any(c.strip() for c in r)]

    if not rows:
        raise ValueError("CSV file is empty.")

    # Detect format: try to parse first cell of first row as float
    try:
        float(rows[0][0].strip())
        is_one_col = True
    except ValueError:
        is_one_col = False

    if is_one_col:
        costs_raw = []
        for row in rows:
            try:
                costs_raw.append(float(row[0].strip()))
            except (ValueError, IndexError):
                pass  # skip blank / header rows
        if len(costs_raw) != len(gen_names):
            raise ValueError(
                f"One-column CSV has {len(costs_raw)} values; expected {len(gen_names)}."
            )
        return {name: c for name, c in zip(gen_names, costs_raw)}
    else:
        # Two-column: skip header if first col matches "gen" or non-numeric
        data_rows = rows
        if rows and rows[0][0].strip().lower() in ("gen", "gen_name", "name", "generator"):
            data_rows = rows[1:]
        result: Dict[str, float] = {}
        for row in data_rows:
            if len(row) < 2:
                continue
            name, cost_str = row[0].strip(), row[1].strip()
            try:
                result[name] = float(cost_str)
            except ValueError:
                raise ValueError(f"Cannot parse cost '{cost_str}' for generator '{name}'.")
        missing = [n for n in gen_names if n not in result]
        if missing:
            raise ValueError(f"CSV missing entries for generators: {', '.join(missing)}")
        return {n: result[n] for n in gen_names}


def prompt_gen_costs(grid_cfg: dict) -> Dict[str, float]:
    """Step 4: show defaults, optionally let user override."""
    defaults = grid_cfg["gen_costs_factory"]()
    gen_names = [g[0] for g in grid_cfg["gen_data"]]

    print(f"\n{_divider()}")
    print("[Step 3] Generator costs")
    print("  Default costs for this grid:")
    for name, cost in defaults.items():
        print(f"    {name}: ${cost:.2f}/MWh")

    if prompt_yes_no("  Use defaults?", default=True):
        return defaults

    print("  Custom cost entry:")
    print("    a. Enter a list of numbers (one per generator, in the order shown above)")
    print("    b. Load from CSV file  (1-col numeric or 2-col gen_name,cost)")
    method = prompt_choice("  Enter choice [a/b]: ", ["a", "b"])

    while True:
        try:
            if method == "a":
                order_str = ", ".join(gen_names)
                raw = input(f"  Enter {len(gen_names)} costs separated by commas\n"
                            f"  (order: {order_str})\n  > ").strip()
                return parse_custom_costs_list(raw, gen_names)
            else:
                path = prompt_filepath("  CSV file path", must_exist=True)
                return parse_custom_costs_csv(path, gen_names)
        except ValueError as exc:
            print(f"  Error: {exc}")
            print("  Please try again.")


# ── Step 5 — Metrics ──────────────────────────────────────────────────────────

METRIC_KEYS = [
    "v_mag",
    "v_ang_deg",
    "p_fr",
    "q_fr",
    "obj_val",
    "converged",
    "solve_time_s",
    "socp_tightness",
    "loop_residuals",
]
_METRIC_NAMES = [
    "Voltage magnitudes  (pu)",
    "Voltage angles      (deg)",
    "Branch P flows      (from-end, pu)",
    "Branch Q flows      (from-end, pu)",
    "Objective value     ($/h)",
    "Convergence status",
    "Solve time          (s)",
    "SOCP tightness      (τ per branch)",
    "Loop residuals      (deg, meshed networks only)",
]


def prompt_metrics() -> List[str]:
    """Step 5: returns list of selected METRIC_KEYS."""
    print(f"\n{_divider()}")
    print("[Step 4] Metrics to display  (comma-separated, or Enter for all)")
    for i, name in enumerate(_METRIC_NAMES, 1):
        print(f"  {i}. {name}")
    idxs = prompt_multi_choice("Enter numbers (e.g. 1,5,6 — or Enter for all): ",
                               len(METRIC_KEYS))
    if not idxs:
        return list(METRIC_KEYS)
    return [METRIC_KEYS[i] for i in idxs]


# ── Step 6 — Save options ─────────────────────────────────────────────────────

def prompt_save_opts(grid_cfg: dict) -> Tuple[Optional[str], Optional[str]]:
    """Step 6: returns (csv_path or None, plot_dir or None)."""
    print(f"\n{_divider()}")
    print("[Step 5] Save outputs")

    csv_path: Optional[str] = None
    if prompt_yes_no("  Save comparison CSV?", default=True):
        csv_path = prompt_filepath("  CSV file path",
                                   default=grid_cfg["csv_default"])

    plot_dir: Optional[str] = None
    if prompt_yes_no("  Save plots as PNG files?", default=False):
        plot_dir = prompt_directory("  Output directory", default=".")

    return csv_path, plot_dir


# ── Solver config resolver ────────────────────────────────────────────────────

def resolve_solver_config(solver_idxs: List[int], grid_cfg: dict) -> dict:
    """Map flat solver index list to compare_solvers params and a display label set.

    Index → solver:
      0 = Circuits NR     1 = Project DC OPF  2 = Project SOCP
      3 = Panda DC OPF    4 = Panda AC OPF
    """
    socp_mode = grid_cfg["socp_mode_default"]
    socp_label = f"socp_{socp_mode}"

    _IDX_TO_LABEL = {
        0: "pp_acpf",
        1: "dc_opf",
        2: socp_label,
        3: "pp_dcopf",
        4: "pp_acopf",
    }

    display_labels: Set[str] = {_IDX_TO_LABEL[i] for i in solver_idxs}
    include_pp_acopf = 4 in solver_idxs

    return {
        "socp_mode": socp_mode,
        "include_pp_acopf": include_pp_acopf,
        "display_labels": display_labels,
        "socp_label": socp_label,
    }


# ── Filtered metric printer ───────────────────────────────────────────────────

def _col_width(values: List[str], header: str, min_w: int = 10) -> int:
    return max(min_w, len(header), max((len(v) for v in values), default=0))


def _fmt(val, precision: int = 6) -> str:
    if val is None:
        return "N/A"
    if isinstance(val, bool):
        return "Yes" if val else "No"
    if isinstance(val, float):
        return f"{val:.{precision}f}"
    return str(val)


def _print_scalar_table(
    results: dict,
    display_labels: Set[str],
    selected_metrics: List[str],
) -> None:
    """Print one summary row per solver for scalar metrics."""
    scalar_keys = [k for k in ("converged", "solve_time_s", "obj_val")
                   if k in selected_metrics]
    if not scalar_keys:
        return

    col_header_map = {
        "converged": "Converged",
        "solve_time_s": "Time (s)",
        "obj_val": "Obj ($/h)",
    }
    labels = [lbl for lbl in _ordered_labels(results) if lbl in display_labels]
    if not labels:
        return

    print("\n  Solver summary:")

    # Collect display values
    rows: List[dict] = []
    for lbl in labels:
        r = results[lbl]
        row = {"solver": _disp(lbl)}
        for k in scalar_keys:
            if k == "converged":
                row[k] = _fmt(r.get("converged"))
            elif k in ("solve_time_s", "obj_val"):
                # pp_acpf has no obj_val (PF mode)
                val = r.get("details", {}).get(k)
                if k == "obj_val" and val is None:
                    row[k] = "N/A"
                else:
                    row[k] = _fmt(val, precision=4)
        rows.append(row)

    # Column widths
    headers = ["Solver"] + [col_header_map[k] for k in scalar_keys]
    col_w = [max(len(h), max(len(row.get(k, "N/A")) for row in rows))
             for h, k in zip(headers[1:], scalar_keys)]
    slbl_w = max(len("Solver"), max(len(r["solver"]) for r in rows))

    sep = "  +" + "-" * (slbl_w + 2) + "+" + "+".join("-" * (w + 2) for w in col_w) + "+"
    header_row = ("  | " + "Solver".ljust(slbl_w) + " | " +
                  " | ".join(h.ljust(w) for h, w in zip(headers[1:], col_w)) + " |")
    print(sep)
    print(header_row)
    print(sep)
    for row in rows:
        cells = [row.get(k, "N/A").ljust(w) for k, w in zip(scalar_keys, col_w)]
        print("  | " + row["solver"].ljust(slbl_w) + " | " + " | ".join(cells) + " |")
    print(sep)


# Remap of internal solver IDs to user-facing display names. Internal IDs
# remain in the results dict (they are produced by compare_solvers) but every
# table, legend, and CSV column header that the user sees uses these names.
_DISPLAY_LABEL = {
    "socp_pf":  "Project SOCP",
    "socp_opf": "Project SOCP",
    "dc_opf":   "Project DC OPF",
    "pp_acpf":  "Circuits NR",
    "pp_dcopf": "Panda DC OPF",
    "pp_acopf": "Panda AC OPF",
}

# Underscored variants used as CSV column-name prefixes (no spaces in headers).
_CSV_LABEL = {
    "socp_pf":  "Project_SOCP",
    "socp_opf": "Project_SOCP",
    "dc_opf":   "Project_DC_OPF",
    "pp_acpf":  "Circuits_NR",
    "pp_dcopf": "Panda_DC_OPF",
    "pp_acopf": "Panda_AC_OPF",
}


def _disp(lbl: str) -> str:
    """Return the user-facing display label for an internal solver ID."""
    return _DISPLAY_LABEL.get(lbl, lbl)


def _rebrand_csv(csv_path: str) -> None:
    """Rewrite the saved CSV so internal solver IDs use the user-facing names.

    Replaces the longest IDs first so substrings of compound names cannot
    collide (e.g. pp_acopf must be replaced before pp_acpf would be a risk).
    """
    with open(csv_path, "r") as f:
        text = f.read()
    for old in sorted(_CSV_LABEL, key=len, reverse=True):
        text = text.replace(old, _CSV_LABEL[old])
    with open(csv_path, "w") as f:
        f.write(text)


def _ordered_labels(results: dict) -> List[str]:
    """Return solver labels in natural compare_solvers order."""
    order = ["socp_pf", "socp_opf", "dc_opf", "pp_acpf", "pp_dcopf", "pp_acopf"]
    present = [k for k in order if k in results]
    extras = [k for k in results if k not in order and not k.startswith("_")]
    return present + extras


def _print_vector_table(
    title: str,
    row_names: List[str],
    data: Dict[str, List[float]],
    display_labels: Set[str],
    results: dict,
    note_fn=None,
    precision: int = 6,
) -> None:
    """Print a name-indexed table with one column per solver."""
    labels = [lbl for lbl in _ordered_labels(results) if lbl in display_labels and lbl in data]
    if not labels:
        return

    name_w = max(len("Name"), max(len(n) for n in row_names))
    col_ws = []
    for lbl in labels:
        note = note_fn(lbl) if note_fn else ""
        header = _disp(lbl) + (f" [{note}]" if note else "")
        vals = [f"{v:.{precision}f}" for v in data[lbl]]
        col_ws.append(max(len(header), max((len(v) for v in vals), default=10)))

    # Build header with notes
    def lbl_header(lbl):
        note = note_fn(lbl) if note_fn else ""
        h = _disp(lbl) + (f" [{note}]" if note else "")
        return h

    sep = ("  +" + "-" * (name_w + 2) + "+" +
           "+".join("-" * (w + 2) for w in col_ws) + "+")
    header_row = ("  | " + "Name".ljust(name_w) + " | " +
                  " | ".join(lbl_header(lbl).ljust(w)
                              for lbl, w in zip(labels, col_ws)) + " |")

    print(f"\n  {title}")
    print(sep)
    print(header_row)
    print(sep)
    for i, name in enumerate(row_names):
        cells = []
        for lbl, w in zip(labels, col_ws):
            v = data[lbl][i] if i < len(data[lbl]) else float("nan")
            cells.append(f"{v:.{precision}f}".ljust(w))
        print("  | " + name.ljust(name_w) + " | " + " | ".join(cells) + " |")
    print(sep)


def print_filtered_results(
    results: dict,
    selected_metrics: List[str],
    display_labels: Set[str],
    bus_names: List[str],
    branch_names: List[str],
) -> None:
    """Print only the user-selected metrics for the selected solver columns."""
    print(f"\n{_divider('═')}")
    print("RESULTS")
    print(_divider("═"))

    if not display_labels:
        print("  (No solvers selected for display.)")

    # Scalar summary
    _print_scalar_table(results, display_labels, selected_metrics)

    # Helper: align arrays (already aligned by compare_solvers via _align_by_name)
    # But results dict stores raw arrays; the alignment was done for CSV only.
    # The arrays in the result dict correspond to circuit ordering for SOCP/DC and
    # the alternate (Circuits) bus ordering for the externally-backed solvers.
    # For a clean terminal view we use circuit ordering (bus_names / branch_names)
    # for SOCP/DC, and tag the externally-backed columns with "alt order" since
    # they may use a different bus ordering.

    circuit_labels = {"socp_pf", "socp_opf", "dc_opf"}

    def _ordering_note(lbl: str) -> str:
        if lbl in circuit_labels:
            return "circuit order"
        return "alt order"

    # Voltage magnitudes
    if "v_mag" in selected_metrics and display_labels:
        data = {lbl: list(results[lbl]["v_mag"])
                for lbl in display_labels if lbl in results}
        # Use bus_names length; pp columns may differ in length — pad with nan
        n = len(bus_names)
        for lbl in data:
            arr = data[lbl]
            data[lbl] = arr[:n] + [float("nan")] * max(0, n - len(arr))
        _print_vector_table("Voltage magnitudes (pu)", bus_names, data,
                            display_labels, results,
                            note_fn=_ordering_note, precision=5)

    # Voltage angles
    if "v_ang_deg" in selected_metrics and display_labels:
        data = {lbl: list(results[lbl]["v_ang_deg"])
                for lbl in display_labels if lbl in results}
        n = len(bus_names)
        for lbl in data:
            arr = data[lbl]
            data[lbl] = arr[:n] + [float("nan")] * max(0, n - len(arr))
        _print_vector_table("Voltage angles (deg)", bus_names, data,
                            display_labels, results,
                            note_fn=_ordering_note, precision=4)

    # Branch P flows
    if "p_fr" in selected_metrics and display_labels:
        data = {lbl: list(results[lbl]["p_fr"])
                for lbl in display_labels if lbl in results}
        n = len(branch_names)
        for lbl in data:
            arr = data[lbl]
            data[lbl] = arr[:n] + [float("nan")] * max(0, n - len(arr))
        _print_vector_table("Branch real power flows P_from (pu)", branch_names, data,
                            display_labels, results,
                            note_fn=_ordering_note, precision=5)

    # Branch Q flows
    if "q_fr" in selected_metrics and display_labels:
        data = {lbl: list(results[lbl]["q_fr"])
                for lbl in display_labels if lbl in results}
        n = len(branch_names)
        for lbl in data:
            arr = data[lbl]
            data[lbl] = arr[:n] + [float("nan")] * max(0, n - len(arr))

        def q_note(lbl: str) -> str:
            if lbl in ("dc_opf", "pp_dcopf"):
                return "Q=0 DC approx"
            return _ordering_note(lbl)

        _print_vector_table("Branch reactive power flows Q_from (pu)", branch_names, data,
                            display_labels, results,
                            note_fn=q_note, precision=5)

    # SOCP tightness
    if "socp_tightness" in selected_metrics:
        tight = results.get("_socp_tightness", {})
        tau_names = tight.get("branch_names")
        tau_vals = tight.get("tau")
        if tau_names is not None and tau_vals is not None:
            socp_was_hidden = not any(lbl.startswith("socp_") for lbl in display_labels)
            note = "  (from internal SOCP run — SOCP column was not selected for display)" \
                if socp_was_hidden else ""
            print(f"\n  SOCP tightness (τ){note}")
            name_w = max(len("Branch"), max(len(n) for n in tau_names))
            print("  +" + "-" * (name_w + 2) + "+" + "-" * 12 + "+" + "-" * 14 + "+")
            print("  | " + "Branch".ljust(name_w) + " | " +
                  "tau".ljust(10) + " | " + "gap (1-tau)".ljust(12) + " |")
            print("  +" + "-" * (name_w + 2) + "+" + "-" * 12 + "+" + "-" * 14 + "+")
            for name, tau in zip(tau_names, tau_vals):
                gap = 1.0 - float(tau)
                print("  | " + name.ljust(name_w) +
                      f" | {float(tau):.8f}   | {gap:+.2e}       |")
            print("  +" + "-" * (name_w + 2) + "+" + "-" * 12 + "+" + "-" * 14 + "+")
            max_gap = tight.get("max_gap", None)
            worst = tight.get("worst_branch", None)
            if max_gap is not None:
                print(f"  Worst branch: {worst}  max gap = {max_gap:.2e}")
        else:
            print("\n  SOCP tightness: not available (SOCP did not converge).")

    # Loop residuals
    if "loop_residuals" in selected_metrics:
        tight = results.get("_socp_tightness", {})
        loop_res = tight.get("loop_residuals_deg", {})
        socp_was_hidden = not any(lbl.startswith("socp_") for lbl in display_labels)
        note = "  (from internal SOCP run)" if socp_was_hidden else ""
        if loop_res:
            print(f"\n  Loop residuals (deg){note}")
            print("  (Non-tree branches only. Nonzero = phase inconsistency around loop.)")
            bw = max(len("Branch"), max(len(b) for b in loop_res))
            print("  +" + "-" * (bw + 2) + "+" + "-" * 14 + "+")
            print("  | " + "Branch".ljust(bw) + " | " + "Residual (°)".ljust(12) + " |")
            print("  +" + "-" * (bw + 2) + "+" + "-" * 14 + "+")
            for branch, res in loop_res.items():
                print("  | " + branch.ljust(bw) + f" | {res:+.4f}".ljust(14) + "  |")
            print("  +" + "-" * (bw + 2) + "+" + "-" * 14 + "+")
            max_lr = tight.get("max_loop_residual_deg", None)
            if max_lr is not None:
                print(f"  Max |loop residual| = {max_lr:.4f}°")
        else:
            if not loop_res and tight.get("branch_names") is not None:
                print("\n  Loop residuals: none (radial network or SOCP did not converge).")
            else:
                print("\n  Loop residuals: not available (SOCP did not converge).")


# ── Plot saving ───────────────────────────────────────────────────────────────

_SOLVER_COLORS = ['#1565C0', '#E53935', '#43A047', '#FB8C00', '#9C27B0', '#00838F']
_SOLVER_MARKERS = ['o', 's', '^', 'D', 'v', 'P']


def _line_plot(
    title: str,
    x_labels: List[str],
    series: Dict[str, list],
    ylabel: str,
    out_path: str,
) -> None:
    """Line-with-markers plot — one line per solver — saved as PNG."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig_w = max(8.0, len(x_labels) * 0.45)
    fig, ax = plt.subplots(figsize=(fig_w, 4.5))
    x = list(range(len(x_labels)))

    for i, (lbl, vals) in enumerate(series.items()):
        ax.plot(x, vals,
                marker=_SOLVER_MARKERS[i % len(_SOLVER_MARKERS)],
                color=_SOLVER_COLORS[i % len(_SOLVER_COLORS)],
                label=lbl, linewidth=1.3, markersize=4)

    ax.set_title(title, fontsize=11, fontweight='bold')
    ax.set_xlabel('Index')
    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    ax.set_xticklabels(x_labels, rotation=55, ha='right', fontsize=7)
    ax.legend(fontsize=8, loc='best')
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  Saved: {out_path}")


def _bar_plot(
    title: str,
    labels: List[str],
    values: List[float],
    ylabel: str,
    out_path: str,
) -> None:
    """Horizontal bar chart for a single series (e.g. objective values)."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, max(3.0, len(labels) * 0.5)))
    colors = _SOLVER_COLORS[: len(labels)]
    bars = ax.barh(labels, values, color=colors, edgecolor='white', height=0.6)
    for bar, val in zip(bars, values):
        if val is not None:
            ax.text(bar.get_width() * 1.01, bar.get_y() + bar.get_height() / 2,
                    f'{val:.2f}', va='center', fontsize=8)
    ax.set_title(title, fontsize=11, fontweight='bold')
    ax.set_xlabel(ylabel)
    ax.invert_yaxis()
    ax.grid(True, axis='x', alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  Saved: {out_path}")


def save_plots(
    results: dict,
    grid_key: str,
    output_dir: str,
    selected_metrics: List[str],
    display_labels: Set[str],
    bus_names: List[str],
    branch_names: List[str],
) -> None:
    """Save one PNG per selected metric that has a plot representation."""
    os.makedirs(output_dir, exist_ok=True)

    # Ordered list of solvers to include in plots
    labels = [lbl for lbl in _ordered_labels(results)
              if lbl in display_labels and lbl in results]

    # ── Voltage magnitudes ────────────────────────────────────────────────
    if 'v_mag' in selected_metrics and labels:
        series = {_disp(lbl): list(results[lbl]['v_mag'])[:len(bus_names)]
                  for lbl in labels}
        _line_plot(
            f'Voltage magnitudes — {grid_key}',
            bus_names, series, '|V| (pu)',
            os.path.join(output_dir, 'fig_voltages.png'),
        )

    # ── Voltage angles ────────────────────────────────────────────────────
    if 'v_ang_deg' in selected_metrics and labels:
        series = {_disp(lbl): list(results[lbl]['v_ang_deg'])[:len(bus_names)]
                  for lbl in labels}
        _line_plot(
            f'Voltage angles — {grid_key}',
            bus_names, series, 'Angle (deg)',
            os.path.join(output_dir, 'fig_angles.png'),
        )

    # ── Branch P flows ────────────────────────────────────────────────────
    if 'p_fr' in selected_metrics and labels:
        series = {_disp(lbl): list(results[lbl]['p_fr'])[:len(branch_names)]
                  for lbl in labels}
        _line_plot(
            f'Branch real power (from-end) — {grid_key}',
            branch_names, series, 'P_fr (pu)',
            os.path.join(output_dir, 'fig_branch_p.png'),
        )

    # ── Branch Q flows ────────────────────────────────────────────────────
    if 'q_fr' in selected_metrics and labels:
        series = {_disp(lbl): list(results[lbl]['q_fr'])[:len(branch_names)]
                  for lbl in labels}
        _line_plot(
            f'Branch reactive power (from-end) — {grid_key}',
            branch_names, series, 'Q_fr (pu)',
            os.path.join(output_dir, 'fig_branch_q.png'),
        )

    # ── Objective value ───────────────────────────────────────────────────
    if 'obj_val' in selected_metrics and labels:
        obj_labels, obj_vals = [], []
        for lbl in labels:
            v = results[lbl].get('details', {}).get('obj_val')
            if v is not None:
                obj_labels.append(_disp(lbl))
                obj_vals.append(v)
        if obj_labels:
            _bar_plot(
                f'Objective values ($/h) — {grid_key}',
                obj_labels, obj_vals, '$/h',
                os.path.join(output_dir, 'fig_objectives.png'),
            )

    # ── SOCP tightness (from plots.py) ───────────────────────────────────
    if 'socp_tightness' in selected_metrics:
        tight = results.get('_socp_tightness', {})
        if tight.get('branch_names') is not None:
            try:
                from plots import plot_socp_tightness
                path = os.path.join(output_dir, 'fig_tightness.png')
                plot_socp_tightness({grid_key: results}, save_path=path)
                print(f"  Saved: {path}")
            except Exception as exc:
                print(f"  Could not save tightness plot: {exc}")


# ── Main session ──────────────────────────────────────────────────────────────

def run_interactive_session() -> None:
    print(_divider("═"))
    print("  PythonPowerFlow — Interactive Solver Comparison")
    print(_divider("═"))
    print("  Compare Project / Circuits / Panda solvers on standard test grids.")
    print("  Press Ctrl-C at any time to exit.")

    # ── Steps 1–2: prompts before heavy imports ────────────────────────────
    grid_num = prompt_grid()
    solver_idxs = prompt_solvers(grid_num)

    # ── Heavy imports ──────────────────────────────────────────────────────
    print(f"\n{_divider()}")
    print("  Loading modules...")
    try:
        from demo_project import (
            make_case14_circuit, make_case14_pandapower, make_gen_limits, make_gen_costs,
            GEN_DATA,
            make_wb5_circuit, make_wb5_pandapower, make_wb5_gen_limits, make_wb5_gen_costs,
            GEN_DATA_WB5,
            make_c22loop_circuit, make_c22loop_pandapower,
            make_c22loop_gen_limits, make_c22loop_gen_costs, make_c22loop_asym_gen_costs,
            GEN_DATA_C22,
            compare_solvers,
        )
    except ImportError as exc:
        print(f"  ERROR: Could not import demo_project.py: {exc}")
        sys.exit(1)

    imports = dict(
        make_case14_circuit=make_case14_circuit,
        make_case14_pandapower=make_case14_pandapower,
        make_gen_limits=make_gen_limits,
        make_gen_costs=make_gen_costs,
        GEN_DATA=GEN_DATA,
        make_wb5_circuit=make_wb5_circuit,
        make_wb5_pandapower=make_wb5_pandapower,
        make_wb5_gen_limits=make_wb5_gen_limits,
        make_wb5_gen_costs=make_wb5_gen_costs,
        GEN_DATA_WB5=GEN_DATA_WB5,
        make_c22loop_circuit=make_c22loop_circuit,
        make_c22loop_pandapower=make_c22loop_pandapower,
        make_c22loop_gen_limits=make_c22loop_gen_limits,
        make_c22loop_gen_costs=make_c22loop_gen_costs,
        make_c22loop_asym_gen_costs=make_c22loop_asym_gen_costs,
        GEN_DATA_C22=GEN_DATA_C22,
    )

    grid_registry = _build_grid_registry(imports)
    grid_cfg = grid_registry[grid_num]
    print(f"  Grid: {grid_cfg['label']}")

    # ── Steps 3–5: cost / metric / save prompts ────────────────────────────
    gen_costs = prompt_gen_costs(grid_cfg)
    selected_metrics = prompt_metrics()
    csv_path, plot_dir = prompt_save_opts(grid_cfg)

    # ── Resolve solver config ──────────────────────────────────────────────
    solver_cfg = resolve_solver_config(solver_idxs, grid_cfg)

    # ── Circuit ordering for display ───────────────────────────────────────
    _circ = grid_cfg["circuit_factory"]()
    bus_names: List[str] = list(_circ.calc_ybus().index)
    branch_names: List[str] = (list(_circ.transmission_lines.keys()) +
                               list(_circ.transformers.keys()))

    # ── CSV path — never None (compare_solvers always opens it) ──────────
    _tmp_csv: Optional[str] = None
    if not csv_path:
        _tmp_csv = tempfile.mktemp(suffix=".csv")
        csv_path = _tmp_csv

    # ── Run solvers ────────────────────────────────────────────────────────
    print(f"\n{_divider()}")
    print("  Running solvers (this may take a few seconds)...")
    gen_limits = grid_cfg["gen_limits_factory"]()
    results = compare_solvers(
        circuit_factory=grid_cfg["circuit_factory"],
        pandapower_factory=grid_cfg["pandapower_factory"],
        gen_limits=gen_limits,
        gen_costs=gen_costs,
        output_csv=csv_path,
        socp_mode=solver_cfg["socp_mode"],
        include_pp_acopf=solver_cfg["include_pp_acopf"],
        v_min=grid_cfg["v_min"],
        v_max=grid_cfg["v_max"],
    )

    # Rebrand internal solver IDs to user-facing names in the saved CSV.
    if csv_path and not _tmp_csv and os.path.exists(csv_path):
        _rebrand_csv(csv_path)

    # Clean up temp CSV if user didn't want a file
    if _tmp_csv and os.path.exists(_tmp_csv):
        os.remove(_tmp_csv)

    # ── Display filtered results ───────────────────────────────────────────
    print_filtered_results(
        results,
        selected_metrics,
        solver_cfg["display_labels"],
        bus_names,
        branch_names,
    )

    # ── Save outputs ───────────────────────────────────────────────────────
    if csv_path and not _tmp_csv:
        print(f"\n  CSV saved to: {os.path.abspath(csv_path)}")

    if plot_dir:
        print(f"\n  Saving plots to: {os.path.abspath(plot_dir)}")
        save_plots(results, grid_cfg["grid_key"], plot_dir,
                   selected_metrics, solver_cfg["display_labels"],
                   bus_names, branch_names)

    print(f"\n{_divider('═')}")
    print("  Done.")
    print(_divider("═"))


def main() -> None:
    try:
        run_interactive_session()
    except KeyboardInterrupt:
        print("\n\n  Interrupted — exiting.")
        sys.exit(0)


if __name__ == "__main__":
    main()
