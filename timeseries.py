from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from powerflow import PowerFlow


@dataclass
class AssignmentConfig:
    """Assignment rules for mapping time-series modifiers to circuit loads."""

    shared_load_names: list[str] | None = None
    shared_modifier_column: str | None = None
    column_to_load: dict[str, str] | None = None


class TimeSeriesPowerFlow:
    """Run repeated power-flow solves across time steps using load modifiers from CSV."""

    def __init__(self) -> None:
        self.profile: pd.DataFrame | None = None
        self.step_column: str | None = None
        self.assignment = AssignmentConfig()
        self.results: pd.DataFrame | None = None

    def load_profile(
        self,
        csv_path: str | Path,
        step_column: str | None = "time",
    ) -> pd.DataFrame:
        """
        Load time-series profile data from CSV.

        Args:
            csv_path: Path to profile CSV.
            step_column: Name of column to use as step identifier.
                If None, DataFrame index is used.

        Returns:
            Loaded profile DataFrame.
        """
        path = Path(csv_path)
        if not path.exists():
            raise FileNotFoundError(f"Profile CSV not found: {path}")

        profile = pd.read_csv(path)
        profile.columns = [str(c).strip() for c in profile.columns]

        if step_column is not None and step_column not in profile.columns:
            raise ValueError(
                f"step_column '{step_column}' is not present in CSV columns {list(profile.columns)}"
            )

        self.profile = profile
        self.step_column = step_column
        return profile

    def assign_shared_modifier(self, load_names: list[str], modifier_column: str = "load") -> None:
        """
        Assign one modifier column to one or more loads.

        Example:
            modifier_column='load', load_names=['LD2', 'LD3']
        """
        if not load_names:
            raise ValueError("load_names must contain at least one load name")
        if not modifier_column or not modifier_column.strip():
            raise ValueError("modifier_column must be a non-empty string")

        self.assignment = AssignmentConfig(
            shared_load_names=[name.strip() for name in load_names],
            shared_modifier_column=modifier_column.strip(),
            column_to_load=None,
        )

    def assign_per_load_modifiers(self, column_to_load: dict[str, str]) -> None:
        """
        Assign separate modifier columns to specific loads.

        Example:
            {'LD2_scale': 'LD2', 'LD3_scale': 'LD3'}
        """
        if not column_to_load:
            raise ValueError("column_to_load must be a non-empty mapping")

        normalized: dict[str, str] = {}
        for col, load_name in column_to_load.items():
            col_s = str(col).strip()
            load_s = str(load_name).strip()
            if not col_s or not load_s:
                raise ValueError("column_to_load keys/values must be non-empty strings")
            normalized[col_s] = load_s

        self.assignment = AssignmentConfig(
            shared_load_names=None,
            shared_modifier_column=None,
            column_to_load=normalized,
        )

    def run(
        self,
        circuit,
        ybus: Any = None,
        tol: float = 1e-3,
        max_iter: int = 50,
    ) -> pd.DataFrame:
        """Execute a time-series simulation and return an aggregated results DataFrame."""
        if self.profile is None:
            raise ValueError("No profile loaded. Call load_profile() first.")

        if ybus is None:
            ybus = circuit.y_bus

        if not hasattr(circuit, "loads") or not hasattr(circuit, "buses"):
            raise TypeError("circuit must expose loads and buses dictionaries")

        assignment_mode = self._get_assignment_mode()
        self._validate_profile_columns(assignment_mode)
        self._validate_assigned_loads_exist(circuit)

        base_loads = {
            load_name: (float(load.mw), float(load.mvar))
            for load_name, load in circuit.loads.items()
        }

        rows: list[dict[str, Any]] = []
        for row_index, row in self.profile.iterrows():
            step_value = self._get_step_value(row_index, row)
            applied_modifiers = self._apply_modifiers_for_row(
                circuit,
                row,
                base_loads,
                assignment_mode,
            )

            solver = PowerFlow()
            solve_result = solver.solve(circuit, ybus=ybus, tol=tol, max_iter=max_iter)

            row_out: dict[str, Any] = {"step": step_value}
            for load_name, modifier in applied_modifiers.items():
                row_out[f"modifier_{load_name}"] = modifier

            bus_names = solve_result["bus_names"]
            voltages = solve_result["voltages"]
            angles_deg = solve_result["angles_deg"]
            for i, bus_name in enumerate(bus_names):
                row_out[f"V_{bus_name}_pu"] = float(voltages[i])
                row_out[f"angle_{bus_name}_deg"] = float(angles_deg[i])

            mismatch_history = solve_result.get("mismatch_history", [])
            row_out["converged"] = bool(solve_result.get("converged", False))
            row_out["iterations"] = int(solve_result.get("iterations", 0))
            row_out["max_mismatch"] = float(mismatch_history[-1]) if mismatch_history else np.nan
            rows.append(row_out)

        # Restore original load values after simulation.
        for load_name, (base_mw, base_mvar) in base_loads.items():
            circuit.loads[load_name].mw = base_mw
            circuit.loads[load_name].mvar = base_mvar

        self.results = pd.DataFrame(rows)
        return self.results

    def save_results_csv(self, output_path: str | Path) -> Path:
        """Save the most recent simulation results DataFrame to CSV."""
        if self.results is None:
            raise ValueError("No results available. Call run() first.")

        path = Path(output_path)
        self.results.to_csv(path, index=False)
        return path

    def _get_assignment_mode(self) -> str:
        if self.assignment.column_to_load:
            return "per_load"
        if self.assignment.shared_load_names and self.assignment.shared_modifier_column:
            return "shared"
        raise ValueError(
            "No load assignment configured. Call assign_shared_modifier() or "
            "assign_per_load_modifiers() before run()."
        )

    def _validate_profile_columns(self, assignment_mode: str) -> None:
        assert self.profile is not None
        if assignment_mode == "shared":
            col = self.assignment.shared_modifier_column
            assert col is not None
            if col not in self.profile.columns:
                raise ValueError(f"Modifier column '{col}' not found in profile")
        else:
            assert self.assignment.column_to_load is not None
            missing = [col for col in self.assignment.column_to_load if col not in self.profile.columns]
            if missing:
                raise ValueError(f"Missing modifier columns in profile: {missing}")

    def _validate_assigned_loads_exist(self, circuit) -> None:
        load_names = set(circuit.loads.keys())

        if self.assignment.shared_load_names is not None:
            missing = [name for name in self.assignment.shared_load_names if name not in load_names]
            if missing:
                raise ValueError(f"Assigned load names not found in circuit: {missing}")

        if self.assignment.column_to_load is not None:
            mapped_loads = list(self.assignment.column_to_load.values())
            missing = [name for name in mapped_loads if name not in load_names]
            if missing:
                raise ValueError(f"Mapped load names not found in circuit: {missing}")

    def _get_step_value(self, row_index: int, row: pd.Series) -> Any:
        if self.step_column is None:
            return row_index
        return row[self.step_column]

    def _apply_modifiers_for_row(
        self,
        circuit,
        row: pd.Series,
        base_loads: dict[str, tuple[float, float]],
        assignment_mode: str,
    ) -> dict[str, float]:
        applied: dict[str, float] = {}

        if assignment_mode == "shared":
            assert self.assignment.shared_modifier_column is not None
            assert self.assignment.shared_load_names is not None
            modifier = float(row[self.assignment.shared_modifier_column])
            if modifier < 0:
                raise ValueError("Load modifier must be non-negative")

            for load_name in self.assignment.shared_load_names:
                base_mw, base_mvar = base_loads[load_name]
                circuit.loads[load_name].mw = base_mw * modifier
                circuit.loads[load_name].mvar = base_mvar * modifier
                applied[load_name] = modifier
            return applied

        assert self.assignment.column_to_load is not None
        for column, load_name in self.assignment.column_to_load.items():
            modifier = float(row[column])
            if modifier < 0:
                raise ValueError("Load modifier must be non-negative")

            base_mw, base_mvar = base_loads[load_name]
            circuit.loads[load_name].mw = base_mw * modifier
            circuit.loads[load_name].mvar = base_mvar * modifier
            applied[load_name] = modifier

        return applied
