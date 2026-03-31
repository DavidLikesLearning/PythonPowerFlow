# circuit.py
from __future__ import annotations
from typing import Dict
import warnings

from bus import BusType
from bus import Bus

from transformer import Transformer
from transmissionline import TransmissionLine
from generator import Generator
from load import Load
from settings import grid_settings

import numpy as np
import pandas as pd

class Circuit:
    """
    Circuit class for power system network modeling.

    This class serves as a container to assemble a complete power system network
    by storing and managing all equipment objects (buses, transformers,
    transmission lines, generators, and loads).

    Attributes:
        name: Identifier for the circuit.
        buses: Dictionary storing Bus objects with bus names as keys.
        transformers: Dictionary storing Transformer objects with transformer names as keys.
        transmission_lines: Dictionary storing TransmissionLine objects with line names as keys.
        generators: Dictionary storing Generator objects with generator names as keys.
        loads: Dictionary storing Load objects with load names as keys.
    """

    def __init__(self, name: str):
        """
        Initialize a Circuit instance.

        Args:
            name: The circuit name (must be a non-empty string).

        Raises:
            ValueError: If name is not a non-empty string.
        """
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string")

        if name != name.strip():
            warnings.warn("Circuit name is stripped in processing. Avoid blank spaces in beginning and end of `name`.")

        self._name = name.strip()
        self._buses : Dict[str, Bus] = {}
        self._transformers : Dict[str, Transformer] = {}
        self._transmission_lines : Dict[str, TransmissionLine] = {}
        self._generators : Dict[str, Generator] = {}
        self._loads: Dict[str, Load] = {}
        self._bus_index: Dict[str, int] = {}
        self._y_bus: pd.DataFrame | None = None

    def __repr__(self) -> str:
        """Return unambiguous representation of Circuit."""
        return f"Circuit(name={self._name!r})"

    def __str__(self) -> str:
        """Return human-readable summary of Circuit."""
        return (
            f"Circuit '{self._name}': "
            f"{len(self._buses)} buses, "
            f"{len(self._transformers)} transformers, "
            f"{len(self._transmission_lines)} transmission lines, "
            f"{len(self._generators)} generators, "
            f"{len(self._loads)} loads"
        )

    # --- name property ---
    @property
    def name(self) -> str:
        """Get circuit name."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Set circuit name."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError("name must be a non-empty string")
        self._name = value.strip()

    # --- Equipment dictionary properties (read-only) ---
    @property
    def buses(self) -> dict:
        """Get buses dictionary."""
        return self._buses

    @property
    def transformers(self) -> dict:
        """Get transformers dictionary."""
        return self._transformers

    @property
    def transmission_lines(self) -> dict:
        """Get transmission lines dictionary."""
        return self._transmission_lines

    @property
    def generators(self) -> dict:
        """Get generators dictionary."""
        return self._generators

    @property
    def loads(self) -> dict:
        """Get loads dictionary."""
        return self._loads

    @property
    def y_bus(self) -> pd.DataFrame:
        """Get Y-bus matrix."""
        if self._y_bus is None:
            raise RuntimeError("Y-bus has not been built yet. Call calc_ybus() first.")
        return self._y_bus

    # --- Add methods ---
    def calc_ybus(self) -> pd.DataFrame:
        """
        Calculate the Y-bus matrix and bus_index mapping from the current buses
        and network elements.

        - Diagonal (i,i): sum of all admittances connected to bus i
          (including shunts from line π-models).
        - Off-diagonal (i,j): admittance between buses i and j if a connection
          exists, else 0. With TransmissionLine, this is the usual negative
          series admittance.
        """
        # No buses: empty Y-bus
        if not self.buses:
            self._bus_index = {}
            self._y_bus = pd.DataFrame(dtype=complex)
            return self._y_bus

        # Define a deterministic bus order (current dict order)
        bus_names = list(self.buses.keys())  # relies on Python 3.7+ ordered dicts
        self._bus_index = {name: idx for idx, name in enumerate(bus_names)}

        n = len(bus_names)
        Y = np.zeros((n, n), dtype=complex)

        for line in (list(self.transmission_lines.values()) +
                list(self.transformers.values())):
            y2 = line.admittance_matrix  # 2x2 DataFrame indexed by [bus1name, bus2name] [file:1]
            b1 = line.bus1_name
            b2 = line.bus2_name

            i = self._bus_index[b1]
            j = self._bus_index[b2]

            # Stamp 2x2 block
            Y[i, i] += y2.loc[b1, b1]
            Y[i, j] += y2.loc[b1, b2]
            Y[j, i] += y2.loc[b2, b1]
            Y[j, j] += y2.loc[b2, b2]

        self._y_bus = pd.DataFrame(Y, index=bus_names, columns=bus_names)
        return self._y_bus


    def add_bus(self, name: str, nominal_kv: float, bus_type: BusType,
                vpu:float = 1.0, delta: float= 0.0) -> None:
        """
        Add a bus to the circuit.

        Args:
            name: Bus name (must be unique within buses).
            nominal_kv: Nominal voltage in kV.
            vpu: set voltage in pu
            delta: set angle in radians

        Raises:
            ValueError: If a bus with the same name already exists.
        """
        if name in self._buses:
            raise ValueError(f"Bus '{name}' already exists in circuit")

        self._buses[name] = Bus(name, nominal_kv, bus_type, vpu, delta)
        self._bus_index[name] = Bus._bus_index

    def add_transformer(self, name: str, bus1_name: str, bus2_name: str,
                        r: float, x: float, g:float=0, b:float=0) -> None:
        """
        Add a transformer to the circuit.

        Args:
            name: Transformer name (must be unique within transformers).
            bus1_name: Primary bus name.
            bus2_name: Secondary bus name.
            r: Series resistance.
            x: Series reactance.
            g: Shunt conductance
            b: Shunt susceptance

        Raises:
            ValueError: If a transformer with the same name already exists.
        """
        if name in self._transformers:
            raise ValueError(f"Transformer '{name}' already exists in circuit")
        if bus1_name not in self._buses or bus2_name not in self._buses:
            raise ValueError(f"{bus1_name} and {bus2_name} are not both in circuit")

        self._transformers[name] = Transformer(name, bus1_name, bus2_name, r=r, x=x, g=g, b=b)
        self._y_bus = None  # invalidate Y-bus; call build_y_bus() to rebuild

    def add_transmission_line(self, name: str, bus1_name: str, bus2_name: str,
                              r: float, x: float, g:float=0, b:float=0) -> None:
        """
        Add a transmission line to the circuit.

        Args:
            name: Line name (must be unique within transmission lines).
            bus1_name: From-bus name.
            bus2_name: To-bus name.
            r: Series resistance.
            x: Series reactance.
            g: Shunt conductance.
            b: Shunt susceptance.

        Raises:
            ValueError: If a transmission line with the same name already exists.
        """
        if name in self._transmission_lines:
            raise ValueError(f"Transmission line '{name}' already exists in circuit")
        if bus1_name not in self._buses or bus2_name not in self._buses:
            raise ValueError(f"{bus1_name} and {bus2_name} are not both in circuit")
        self._transmission_lines[name] = TransmissionLine(name, bus1_name, bus2_name, r=r, x=x, b=b, g=g)
        self._y_bus = None  # invalidate Y-bus; call build_y_bus() to rebuild

    def add_generator(self, name: str, bus_name: str,
                      voltage_setpoint: float, mw_setpoint: float) -> None:
        """
        Add a generator to the circuit.

        Args:
            name: Generator name (must be unique within generators).
            bus_name: Bus name where generator is connected.
            voltage_setpoint: Voltage setpoint in per unit.
            mw_setpoint: Active power setpoint in MW.

        Raises:
            ValueError: If a generator with the same name already exists.
        """
        if name in self._generators:
            raise ValueError(f"Generator '{name}' already exists in circuit")

        if bus_name not in self.buses:
            raise ValueError(f"Bus '{bus_name}' doesn't exists in circuit")
        self._generators[name] = Generator(name, bus_name, mw_setpoint, voltage_setpoint)
        self.buses[bus_name].vpu = voltage_setpoint

    def add_load(self, name: str, bus_name: str, mw: float, mvar: float) -> None:
        """
        Add a load to the circuit.

        Args:
            name: Load name (must be unique within loads).
            bus_name: Bus name where load is connected.
            mw: Active power in MW.
            mvar: Reactive power in MVAr.
        Raises:
            ValueError: If a load with the same name already exists.
        """
        if name in self._loads:
            raise ValueError(f"Load '{name}' already exists in circuit")
        self._loads[name] = Load(name, bus_name, mw, mvar)

    def _calc_Pi(self, i, ybus, angles, voltages):
        """Real power injection at bus i (Milestone 6, Eq. 2)."""
        Vi = voltages[i]
        Pi = 0.0
        for j in range(ybus.shape[0]):
            dij = angles[i] - angles[j]
            Pi += voltages[j] * (ybus[i, j].real * np.cos(dij) +
                                  ybus[i, j].imag * np.sin(dij))
        return Vi * Pi

    def _calc_Qi(self, i, ybus, angles, voltages):
        """Reactive power injection at bus i (Milestone 6, Eq. 3)."""
        Vi = voltages[i]
        Qi = 0.0
        for j in range(ybus.shape[0]):
            dij = angles[i] - angles[j]
            Qi += voltages[j] * (ybus[i, j].real * np.sin(dij) -
                                  ybus[i, j].imag * np.cos(dij))
        return Vi * Qi

    def _get_data(self):
        """
        Extract and return consistently ordered arrays from the circuit.

        Returns:
            buses      : dict[str, Bus]
            bus_names  : list[str] sorted by _bus_index (matches Y-bus row/col order)
            ybus       : np.ndarray (N x N, complex)
            angles     : np.ndarray (N,) voltage angles in radians
            voltages   : np.ndarray (N,) voltage magnitudes in per-unit
        """
        buses = self.buses
        # Sort names by their Y-bus index so array positions align with Y-bus
        bus_names = sorted(buses.keys(),
                           key=lambda n: self._bus_index[n])
        ybus = self.y_bus.values  # numpy complex array
        angles = np.array([buses[n].delta for n in bus_names])
        voltages = np.array([buses[n].vpu for n in bus_names])
        return buses, bus_names, ybus, angles, voltages

    def _pv_buses(self, bus_names, buses):
        """Return bus names (in order) for all non-slack buses."""
        return [n for n in bus_names
                if buses[n].bus_type != BusType.Slack]

    def _pq_buses(self, bus_names, buses):
        """Return bus names (in order) for PQ buses only."""
        return [n for n in bus_names
                if buses[n].bus_type == BusType.PQ]

    def _calc_J1(self, bus_names, buses, ybus, angles, voltages):
        """
        Compute J1 = dP/d(delta).

        Shape: (N_PV) x (N_PV)

        Formulas:
          Off-diagonal (i != k):
              J1[i,k] = Vi * Vk * (Gik*sin(di - dk) - Bik*cos(di - dk))
          Diagonal (i == k):
              J1[i,i] = -Qi - Bii * Vi^2
        """
        idx     = self._bus_index   # name -> global index
        pv_list = self._pv_buses(bus_names, buses)
        size    = len(pv_list)
        J1      = np.zeros((size, size))

        for row, ni in enumerate(pv_list):
            i  = idx[ni]
            Vi = voltages[i]
            Qi = self._calc_Qi(i, ybus, angles, voltages)
            Bii = ybus[i, i].imag

            for col, nk in enumerate(pv_list):
                k = idx[nk]
                if i == k:
                    J1[row, col] = -Qi - Bii * Vi**2
                else:
                    Vk  = voltages[k]
                    dik = angles[i] - angles[k]
                    Gik = ybus[i, k].real
                    Bik = ybus[i, k].imag
                    J1[row, col] = Vi * Vk * (Gik * np.sin(dik)
                                              - Bik * np.cos(dik))
        return J1

    def _calc_J2(self, bus_names, buses, ybus, angles, voltages):
        """
        Compute J2 = dP/d|V|.

        Shape: (N_PV) x (N_PQ)

        Formulas:
          Off-diagonal (i != k):
              J2[i,k] = Vi * (Gik*cos(di - dk) + Bik*sin(di - dk))
          Diagonal (i == k, only possible when bus i is PQ):
              J2[i,i] = Pi/Vi + Gii * Vi
        """
        idx     = self._bus_index
        pv_list = self._pv_buses(bus_names, buses)
        pq_list = self._pq_buses(bus_names, buses)
        J2      = np.zeros((len(pv_list), len(pq_list)))

        for row, ni in enumerate(pv_list):
            i  = idx[ni]
            Vi = voltages[i]
            Pi = self._calc_Pi(i, ybus, angles, voltages)
            Gii = ybus[i, i].real

            for col, nk in enumerate(pq_list):
                k = idx[nk]
                if i == k:
                    J2[row, col] = Pi / Vi + Gii * Vi
                else:
                    Vk  = voltages[k]
                    dik = angles[i] - angles[k]
                    Gik = ybus[i, k].real
                    Bik = ybus[i, k].imag
                    J2[row, col] = Vi * (Gik * np.cos(dik)
                                         + Bik * np.sin(dik))
        return J2

    def _calc_J3(self, bus_names, buses, ybus, angles, voltages):
        """
        Compute J3 = dQ/d(delta).

        Shape: (N_PQ) x (N_PV)

        Formulas:
          Off-diagonal (i != k):
              J3[i,k] = -Vi * Vk * (Gik*cos(di - dk) + Bik*sin(di - dk))
          Diagonal (i == k):
              J3[i,i] = Pi - Gii * Vi^2
        """
        idx     = self._bus_index
        pv_list = self._pv_buses(bus_names, buses)
        pq_list = self._pq_buses(bus_names, buses)
        J3      = np.zeros((len(pq_list), len(pv_list)))

        for row, ni in enumerate(pq_list):
            i  = idx[ni]
            Vi = voltages[i]
            Pi = self._calc_Pi(i, ybus, angles, voltages)
            Gii = ybus[i, i].real

            for col, nk in enumerate(pv_list):
                k = idx[nk]
                if i == k:
                    J3[row, col] = Pi - Gii * Vi**2
                else:
                    Vk  = voltages[k]
                    dik = angles[i] - angles[k]
                    Gik = ybus[i, k].real
                    Bik = ybus[i, k].imag
                    J3[row, col] = -Vi * Vk * (Gik * np.cos(dik)
                                                + Bik * np.sin(dik))
        return J3

    def _calc_J4(self, bus_names, buses, ybus, angles, voltages):
        """
        Compute J4 = dQ/d|V|.

        Shape: (N_PQ) x (N_PQ)

        Formulas:
          Off-diagonal (i != k):
              J4[i,k] = Vi * (Gik*sin(di - dk) - Bik*cos(di - dk))
          Diagonal (i == k):
              J4[i,i] = Qi/Vi - Bii * Vi
        """
        idx     = self._bus_index
        pq_list = self._pq_buses(bus_names, buses)
        size    = len(pq_list)
        J4      = np.zeros((size, size))

        for row, ni in enumerate(pq_list):
            i  = idx[ni]
            Vi = voltages[i]
            Qi = self._calc_Qi(i, ybus, angles, voltages)
            Bii = ybus[i, i].imag

            for col, nk in enumerate(pq_list):
                k = idx[nk]
                if i == k:
                    J4[row, col] = Qi / Vi - Bii * Vi
                else:
                    Vk  = voltages[k]
                    dik = angles[i] - angles[k]
                    Gik = ybus[i, k].real
                    Bik = ybus[i, k].imag
                    J4[row, col] = Vi * (Gik * np.sin(dik)
                                         - Bik * np.cos(dik))
        return J4

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def _calc_jacobian(self):
        """
        Assemble and return the full (2N - 2 - N_PV) x (2N - 2 - N_PV) Jacobian.

        Row/column ordering matches the mismatch vector from _compute_mismatch():
            [ dP_bus1, ..., dP_busN (non-slack PV) | dQ_bus1, ..., dQ_busM (PQ only) ]
        sorted by bus index (ascending).

        Returns:
            J : np.ndarray of shape (2N - 2 - N_PV, 2N - 2 - N_PV)
        """
        buses, bus_names, ybus, angles, voltages = self._get_data()

        J1 = self._calc_J1(bus_names, buses, ybus, angles, voltages)
        J2 = self._calc_J2(bus_names, buses, ybus, angles, voltages)
        J3 = self._calc_J3(bus_names, buses, ybus, angles, voltages)
        J4 = self._calc_J4(bus_names, buses, ybus, angles, voltages)

        # Block-assemble: top row = [J1 | J2], bottom row = [J3 | J4]
        J = np.block([[J1, J2],
                      [J3, J4]])
        return J

    def _calc_mismatch(self) -> np.ndarray:
        """
        Mismatch equations (per-unit):
            ΔP_i = P_spec_i - P_calc_i   for all non-slack PV buses
            ΔQ_i = Q_spec_i - Q_calc_i   for PQ buses only

        P_spec / Q_spec sources (net scheduled injection, converted via sbase):
            PQ bus  →  P_spec = -Σ load.mw   / sbase   (loads withdraw power)
                       Q_spec = -Σ load.mvar / sbase
            PV bus  →  P_spec = (Σ gen.mw_setpoint - Σ load.mw) / sbase
                       (no Q_spec — voltage magnitude is controlled)

        Vector ordering matches the Jacobian assembled in calc_jacobian():
            [ ΔP_bus1, …, ΔP_busM  (all non-slack, sorted by bus index)
              ΔQ_bus1, …, ΔQ_busK  (PQ buses only,  sorted by bus index) ]

        Returns:
            f : np.ndarray of shape (N_PV + N_PQ,)
        """
        buses, bus_names, ybus, angles, voltages = self._get_data()
        sbase = grid_settings.sbase
        idx = self._bus_index

        pv_list = self._pv_buses(bus_names, buses)
        pq_list = self._pq_buses(bus_names, buses)

        # --- Aggregate scheduled MW/MVAr per bus ---------------------------------
        p_load = {n: 0.0 for n in bus_names}
        q_load = {n: 0.0 for n in bus_names}
        p_gen = {n: 0.0 for n in bus_names}

        for load in self._loads.values():
            p_load[load.bus_name] += load.mw
            q_load[load.bus_name] += load.mvar

        for gen in self._generators.values():
            p_gen[gen.bus_name] += gen.mw_setpoint

        # --- ΔP for every non-slack PV bus ------------------------------------------
        delta_P = np.zeros(len(pv_list))
        for row, name in enumerate(pv_list):
            i = idx[name]
            bus = buses[name]

            if bus.bus_type == BusType.PQ:
                p_spec = -p_load[name] / sbase  # load withdraws power
            else:
                p_spec = (p_gen[name] - p_load[name]) / sbase  # net PV injection

            p_calc = self._calc_Pi(i, ybus, angles, voltages)
            delta_P[row] = p_spec - p_calc

        # --- ΔQ for PQ buses only ------------------------------------------------
        delta_Q = np.zeros(len(pq_list))
        for row, name in enumerate(pq_list):
            i = idx[name]
            q_spec = -q_load[name] / sbase
            q_calc = self._calc_Qi(i, ybus, angles, voltages)
            delta_Q[row] = q_spec - q_calc

        return np.concatenate([delta_P, delta_Q])

    def newton_raphson_step(self, mismatch, jacobian):
        """
        Solve J·Δx = f for Newton-Raphson correction vectors.

        Args:
            mismatch  : np.ndarray (n,)  — power mismatch vector f from _calc_mismatch()
            jacobian  : np.ndarray (n,n) — Jacobian matrix J from _calc_jacobian()

        Returns:
            angle_corrections    : np.ndarray — Δδ for every non-slack bus (PV + PQ)
            voltage_corrections  : np.ndarray — Δ|V| for PQ buses only
            pv_list              : list[str]  — non-slack bus names (angle correction index)
            pq_list              : list[str]  — PQ bus names (voltage correction index)
        """
        buses, bus_names, ybus, angles, voltages = self._get_data()
        pv_list = self._pv_buses(bus_names, buses)  # all non-slack (PV + PQ)
        pq_list = self._pq_buses(bus_names, buses)  # PQ only

        dx = np.linalg.solve(jacobian, mismatch)

        # mismatch / dx layout: [ΔP non-slack | ΔQ PQ-only]
        # → dx layout:          [Δδ  non-slack | Δ|V| PQ-only]
        n_nonslock = len(pv_list)
        angle_corrections = dx[:n_nonslock]  # Δδ  — one per non-slack bus
        voltage_corrections = dx[n_nonslock:]  # Δ|V| — one per PQ bus

        return angle_corrections, voltage_corrections, pv_list, pq_list

    def apply_bus_updates(self, angle_corrections, voltage_corrections, pv_list, pq_list):
        """
        Apply Newton-Raphson corrections to bus objects.

        Bus-type rules (per Milestone 8):
          Slack → no update (not in pv_list or pq_list)
          PV    → update δ only (in pv_list, but NOT in pq_list)
          PQ    → update both δ and |V| (in both lists)

        Args:
            angle_corrections   : np.ndarray — Δδ aligned with pv_list
            voltage_corrections : np.ndarray — Δ|V| aligned with pq_list
            pv_list             : list[str]  — non-slack bus names (from newton_raphson_step)
            pq_list             : list[str]  — PQ bus names      (from newton_raphson_step)
        """
        buses = self.buses

        # Update voltage angles for every non-slack bus (PV and PQ)
        for i, name in enumerate(pv_list):
            bus = buses[name]
            bus.delta = bus.delta + angle_corrections[i]

        # Update voltage magnitudes for PQ buses only
        for i, name in enumerate(pq_list):
            bus = buses[name]
            bus.vpu = bus.vpu + voltage_corrections[i]

    def run_power_flow(self, tol=0.001, max_iter=50, flat_start=False,
                       msg = False):
        """
        Solve the power flow iteratively using Newton-Raphson.

        Flat start (default): all non-slack angles → 0.0 rad,
                              all PQ bus voltages  → 1.0 pu.
        PV bus voltages are left at their generator setpoint.

        Convergence criterion: max(|f|) < tol  (checked after each update).

        Args:
            tol        : float — mismatch convergence tolerance (default 1e-3)
            max_iter   : int   — maximum number of NR iterations  (default 50)
            flat_start : bool  — reset voltages/angles before iterating (default True)

        Returns:
            True if converged, False otherwise.
        """
        # ── Flat start initialisation ────────────────────────────────────────────
        if flat_start:
            for bus in self.buses.values():
                if bus.bus_type != BusType.Slack:
                    bus.delta=0.0
                if bus.bus_type == BusType.PQ:
                    bus.vpu=1.0

        # ── Check initial mismatch before any updates ────────────────────────────
        mismatch = self._calc_mismatch()
        max_mm = np.max(np.abs(mismatch))
        if msg:
            print(f"  Iter   0 | max |f| = {max_mm:.6e}  (initial)")

        if max_mm < tol:
            print("  Initial guess already satisfies convergence tolerance.")
            return True

        # ── Newton-Raphson iteration loop ────────────────────────────────────────
        for iteration in range(1, max_iter + 1):

            # Step 1 – compute Jacobian at current operating point
            jacobian = self._calc_jacobian()

            # Step 2 – solve J·Δx = f; get corrections + bus index lists
            angle_corr, volt_corr, pv_list, pq_list = self.newton_raphson_step(
                mismatch, jacobian
            )

            # Step 3 – apply corrections to each bus
            self.apply_bus_updates(angle_corr, volt_corr, pv_list, pq_list)

            # Step 4 – recompute mismatch and check convergence
            mismatch = self._calc_mismatch()
            max_mm = np.max(np.abs(mismatch))
            if msg:
                print(f"  Iter {iteration:3d} | max |f| = {max_mm:.6e}")

            if max_mm < tol:
                print(f"\n  ✓ Converged in {iteration} Newton-Raphson iteration(s).")
                return True

        # ── Non-convergence ──────────────────────────────────────────────────────
        warnings.warn(
            f"Newton-Raphson did not converge after {max_iter} iterations. "
            f"Final max mismatch = {max_mm:.6e}"
        )
        return False

    def _run_single_power_flow(self, tol=0.001, max_iter=50, flat_start=False,
                               msg = False):
        """
        One iteration of Newton-Raphson.

        Flat start (default): all non-slack angles → 0.0 rad,
                              all PQ bus voltages  → 1.0 pu.
        PV bus voltages are left at their generator setpoint.

        Args:
            tol        : float — mismatch convergence tolerance (default 1e-3)
            max_iter   : int   — maximum number of NR iterations  (default 50)
            flat_start : bool  — reset voltages/angles before iterating (default True)

        Returns:
            True if converged, False otherwise.
        """
        # ── Flat start initialisation ────────────────────────────────────────────
        if flat_start:
            for bus in self.buses.values():
                if bus.bus_type != BusType.Slack:
                    bus.delta = 0.0
                if bus.bus_type == BusType.PQ:
                    bus.vpu = 1.0

        mismatch = self._calc_mismatch()
        max_mm = np.max(np.abs(mismatch))
        if msg:
            print(f"  Iter   0 | max |f| = {max_mm:.6e}  (initial)")

        # ── Newton-Raphson once ────────────────────────────────────────

        # compute Jacobian at current operating point
        jacobian = self._calc_jacobian()

        # solve J·Δx = f; get corrections + bus index lists
        angle_corr, volt_corr, pv_list, pq_list = self.newton_raphson_step(
            mismatch, jacobian
        )

        # Step 3 – apply corrections to each bus
        self.apply_bus_updates(angle_corr, volt_corr, pv_list, pq_list)

        # Step 4 – recompute mismatch and check convergence
        mismatch = self._calc_mismatch()
        max_mm = np.max(np.abs(mismatch))
        if msg:
            print(f"  Iter {1:3d} | max |f| = {max_mm:.6e}")

def case6_9():
    """Build the 5-bus example 6.9 from the Power System Analysis book,
    compare the Y-bus matrix to the CSV, and assert numerical equality."""
    circuit = Circuit("5-Bus Example 6.9")
    circuit.add_bus("One", 15.0,bus_type=BusType.Slack)
    circuit.add_bus("Two", 345.0,bus_type=BusType.PQ)
    circuit.add_bus("Three", 15.0,bus_type=BusType.PV, vpu = 1.05)
    circuit.add_bus("Four", 345.0,bus_type=BusType.PQ)
    circuit.add_bus("Five", 345.0,bus_type=BusType.PQ)
    circuit.add_transmission_line("L42", "Four", "Two", r=0.009, x=0.1,  b=1.72)
    circuit.add_transmission_line("L52", "Five", "Two", r=0.0045, x=0.05, b=0.88)
    circuit.add_transmission_line("L54", "Five", "Four", r=0.00225, x=0.025, b=0.44)
    circuit.add_transformer("T15", "One", "Five", r=0.0015, x=0.02)
    circuit.add_transformer("T34", "Three", "Four", r=0.00075, x=0.01)

    circuit.add_load('TwoL', 'Two', 800, 280)
    circuit.add_load('ThreeL', 'Three', 80, 40)
    circuit.add_generator('OneG', 'One', 1.0, 395)
    circuit.add_generator('ThreeG', 'Three', 1.05, 520)

    circuit.calc_ybus()
    return circuit

def _jacobian_labels(circuit):
    """Return (row_labels, col_labels) matching calc_jacobian()'s layout.

    Layout
    ------
    Rows : dP/<bus>  for every non-slack bus  (pvbuses order)
           dQ/<bus>  for every PQ bus          (pqbuses order)
    Cols : delta_<bus>   for every non-slack bus  (pvbuses order)
           voltmag_<bus> for every PQ bus          (pqbuses order)
    """
    buses, busnames, _, _, _ = circuit._get_data()
    pv_list = circuit._pv_buses(busnames, buses)
    pq_list = circuit._pq_buses(busnames, buses)

    row_labels = [f"dP/{n}" for n in pv_list] + [f"dQ/{n}" for n in pq_list]
    col_labels = [f"delta_{n}" for n in pv_list] + [f"voltmag_{n}" for n in pq_list]
    return row_labels, col_labels

def compare_jacobians(circuit, excel_path: str, tol: float = 1e-2):
    """
    Compare computed Jacobian against a reference Excel.
    Both matrices are aligned positionally — no label matching.

    Canonical order
    ---------------
    Rows : dP for non-slack buses (ascending bus number)
           dQ for PQ buses        (ascending bus number)
    Cols : |V| for PQ buses       (ascending bus number)
           delta for non-slack buses (ascending bus number)
    """
    buses, bus_names, ybus, angles, voltages = circuit._get_data()
    idx     = circuit._bus_index          # name -> 0-based insertion index
    pv_list = circuit._pv_buses(bus_names, buses)   # non-slack, already sorted
    pq_list = circuit._pq_buses(bus_names, buses)   # PQ only,   already sorted
    n_pv, n_pq = len(pv_list), len(pq_list)

    # 1-indexed bus numbers aligned with the reference Excel numbering
    bus_num   = {n: idx[n] + 1 for n in bus_names}
    slack_set = {bus_num[n] for n in bus_names
                 if buses[n].bus_type == BusType.Slack}
    pq_nums   = sorted(bus_num[n] for n in pq_list)
    pv_nums   = sorted(bus_num[n] for n in pv_list)

    # ── Generated Jacobian ──────────────────────────────────────────────
    # _calc_jacobian() col layout: [delta pv_list... | voltmag pq_list...]
    # Desired layout:              [voltmag pq_list... | delta pv_list...]
    J_raw  = circuit._calc_jacobian()
    col_perm = list(range(n_pv, n_pv + n_pq)) + list(range(n_pv))
    J_computed = J_raw[:, col_perm]

    # ── Reference Excel ─────────────────────────────────────────────────
    # header=1  → skip row-0 ("Bus","Unnamed:1",...) and use row-1 as header
    #             giving cols: "Name","Jacobian Equation","Angle Bus X","Volt Mag Bus X"
    # index_col=0 → bus numbers (1-5) become the index
    ref_raw = pd.read_excel(excel_path, header=1, index_col=0)

    # dP rows: "Real Power ..." entries, excluding the slack bus
    dp_mask = (ref_raw["Jacobian Equation"].str.contains("Real Power", na=False) &
               ~ref_raw.index.isin(slack_set))
    dp_part = ref_raw[dp_mask].sort_index()   # ascending bus number

    # dQ rows: "Reactive Power" entries (PQ buses only)
    dq_mask = ref_raw["Jacobian Equation"].str.contains("Reactive Power", na=False)
    dq_part = ref_raw[dq_mask].sort_index()   # ascending bus number

    # Select & reorder columns to match canonical [|V| PQ | delta non-slack]
    volt_cols  = [f"Volt Mag Bus {b}" for b in pq_nums]
    angle_cols = [f"Angle Bus {b}"    for b in pv_nums]
    J_ref = (pd.concat([dp_part, dq_part])[volt_cols + angle_cols]
               .astype(float)
               .fillna(0.0)      # NaN in reference = no coupling = 0
               .values)

    # ── Element-wise comparison ─────────────────────────────────────────
    diff  = J_computed - J_ref
    match = bool(np.all(np.abs(diff) <= tol))

    # Human-readable labels (for display only — not used for alignment)
    row_labels = ([f"dP/Bus{bus_num[n]}" for n in pv_list] +
                  [f"dQ/Bus{bus_num[n]}" for n in pq_list])
    col_labels = ([f"|V|_Bus{b}" for b in pq_nums] +
                  [f"d_Bus{b}"   for b in pv_nums])

    computed_df = pd.DataFrame(J_computed, index=row_labels, columns=col_labels)
    ref_df_out  = pd.DataFrame(J_ref,      index=row_labels, columns=col_labels)
    diff_df     = pd.DataFrame(diff,        index=row_labels, columns=col_labels)

    return match, diff_df, J_computed, J_ref

def compare_mismatch(
    circuit,
    excel_path: str,
    tol: float = 1.0,
    sheet_name: str = "Sheet1"
):
    """
    Compare the mismatch vector produced by _calc_mismatch() against a
    reference Excel file (format: mismatch0_case69-2.xlsx).

    The circuit mismatch is computed in per-unit and scaled by ``sbase``
    to match the MW / Mvar values stored in the reference file.

    Excel layout expected
    ---------------------
    Row 0  : "Bus" (merged title — skipped)
    Row 1  : Number | Name | Area Name | Type |
              Mismatch MW | Mismatch Mvar | Mismatch MVA   ← used as header
    Row 2+ : one row per bus

    Mismatch vector layout from _calc_mismatch()
    --------------------------------------------
    [ ΔP  for all non-slack buses  (sorted by bus index)  ]
    [ ΔQ  for PQ buses only        (sorted by bus index)  ]

    Reconstruction per bus
    ----------------------
    Slack   → ΔP_MW = 0,    ΔQ_Mvar = 0   (excluded from NR mismatch)
    PV      → ΔP_MW = f[i], ΔQ_Mvar = 0   (voltage is controlled)
    PQ      → ΔP_MW = f[i], ΔQ_Mvar = f[j]

    Parameters
    ----------
    circuit    : Circuit instance (Y-bus must be built, buses initialised)
    excel_path : Path to the reference .xlsx / .xls file
    tol        : Absolute tolerance in MW or Mvar (default 1.0)
    sheet_name : Excel sheet to read (default "Sheet1")

    Returns
    -------
    match     : bool        — True when every |computed - reference| ≤ tol
    result_df : DataFrame   — per-bus table with computed, reference and
                              difference columns for both ΔP and ΔQ
    diff_df   : DataFrame   — only the difference columns (ΔP_diff, ΔQ_diff)
    """
    sbase = grid_settings.sbase  # MVA base (typically 100)

    # ── Compute mismatch and retrieve bus ordering ──────────────────────
    mismatch_pu = circuit._calc_mismatch()          # shape: (n_pv + n_pq,)

    buses, bus_names, _, _, _ = circuit._get_data()
    pv_list = circuit._pv_buses(bus_names, buses)   # all non-slack (PV + PQ)
    pq_list = circuit._pq_buses(bus_names, buses)   # PQ only

    n_pv = len(pv_list)

    # Scale from per-unit to MW / Mvar
    delta_P_mw   = mismatch_pu[:n_pv] * sbase       # one entry per non-slack bus
    delta_Q_mvar = mismatch_pu[n_pv:] * sbase        # one entry per PQ bus

    # Build per-bus lookup dictionaries  {bus_name: value}
    computed_DeltaP = {name: delta_P_mw[i]   for i, name in enumerate(pv_list)}
    computed_DeltaQ = {name: delta_Q_mvar[i] for i, name in enumerate(pq_list)}

    # ── Read the reference Excel ────────────────────────────────────────
    ref = pd.read_excel(
        excel_path,
        sheet_name=sheet_name,
        header=1,           # row-1 ("Number", "Name", …) is the column header
        index_col=None,
    )
    ref.columns = [
        "Number", "Name", "Area", "Type",
        "Ref_DelP_MW", "Ref_DelQ_Mvar", "Ref_DelS_MVA",
    ]
    ref = ref.dropna(subset=["Name"])  # remove any stray blank rows

    # ── Align computed values onto the reference table row by row ───────
    computed_DeltaP_col, computed_DeltaQ_col = [], []

    for _, row in ref.iterrows():
        name = str(row["Name"]).strip()
        bus  = buses.get(name)

        if bus is None:                          # bus not found in circuit
            computed_DeltaP_col.append(float("nan"))
            computed_DeltaQ_col.append(float("nan"))
            continue

        if bus.bus_type == BusType.Slack:        # slack excluded from NR mismatch
            computed_DeltaP_col.append(0.0)
            computed_DeltaQ_col.append(0.0)
        elif bus.bus_type == BusType.PV:         # PV: ΔP only, voltage is fixed
            computed_DeltaP_col.append(computed_DeltaP.get(name, float("nan")))
            computed_DeltaQ_col.append(0.0)
        else:                                    # PQ: both ΔP and ΔQ
            computed_DeltaP_col.append(computed_DeltaP.get(name, float("nan")))
            computed_DeltaQ_col.append(computed_DeltaQ.get(name, float("nan")))

    ref = ref.copy()
    ref["Comp_DelP_MW"]   = computed_DeltaP_col
    ref["Comp_DelQ_Mvar"] = computed_DeltaQ_col
    ref["Diff_DelP_MW"]   = ref["Comp_DelP_MW"]   - ref["Ref_DelP_MW"]
    ref["Diff_DelQ_Mvar"] = ref["Comp_DelQ_Mvar"] - ref["Ref_DelQ_Mvar"]

    # ── Evaluate tolerance ──────────────────────────────────────────────
    diffs = ref[["Diff_DelP_MW", "Diff_DelQ_Mvar"]].dropna()
    match = bool((diffs.abs() <= tol).all().all())

    # ── Build output DataFrames ─────────────────────────────────────────
    display_cols = [
        "Number", "Name", "Type",
        "Ref_DelP_MW",   "Comp_DelP_MW",   "Diff_DelP_MW",
        "Ref_DelQ_Mvar", "Comp_DelQ_Mvar", "Diff_DelQ_Mvar",
    ]
    result_df = ref[display_cols].reset_index(drop=True)

    return match, result_df

def test_shape_powerflow():
    circuit = case6_9()
    mismatch = circuit._calc_mismatch()
    jacobian = circuit._calc_jacobian()
    # print("Mismatch, Jacobian shapes:\n")
    # print(mismatch.shape, jacobian.shape)
    assert mismatch.shape[0] == 7, "Need a Delta P for all non Slack buses and Delta Q for all PQ buses"
    assert mismatch.shape[0]==jacobian.shape[0], "Mismatch, Jacobian shapes do not match"
    # print("Mismatch, Jacobian values:\n")
    # print(mismatch,'\n', jacobian)

def test_case6_9_convergence():
    circuit = case6_9()
    tol = 1e-5
    circuit.run_power_flow(tol = tol, flat_start=False, msg= True)
    final_mis = circuit._calc_mismatch()
    assert np.linalg.norm(final_mis)<tol, "Mismatch at final mismatch"

def test_case6_9_final_vpu_delta():
    circuit = case6_9()
    tol = 1e-5
    circuit.run_power_flow(tol=tol, flat_start=False, msg=True)
    buses, bus_names, ybus, angles, voltages = circuit._get_data()
    print('final angles (degz)', np.rad2deg(angles) )
    print('final voltages', voltages)

def test_case6_9_start_vpu_delta():
    circuit = case6_9()
    _, _, _, angles, voltages= circuit._get_data( )
    assert np.linalg.norm(
        angles - np.zeros(5))< 0.001, "angles start wrong"
    assert np.linalg.norm(
        voltages - np.array([1,1,1.05,1,1]))< 0.001, "voltages start wrong"

def test_mismatch_flat_start():
    circuit = case6_9()
    match, _ = compare_mismatch(
        circuit, "mismatch0_case69.xlsx", tol = .01)
    assert match, "Mismatches disagree from beginning"

def test_orig_jacobian():
    circuit = case6_9()
    # print(circuit._calc_jacobian())

    match, diff, Jraw, Jref = compare_jacobians(
        circuit,'jacobian0_case69.xlsx', tol = 0.01)
    assert match, "Jacobian disagree from beginning"

def test_newton_raphson_steps():
    circuit = case6_9()
    circuit._run_single_power_flow()
    match_j, diff_j, _, _ = compare_jacobians(
        circuit,'jacobian1_case69.xlsx', tol = 0.01)
    match_m, mis_df = compare_mismatch(
        circuit, "mismatch1_case69.xlsx", tol = 0.01)
    # print("jacobian diff:\n",diff_j)
    # print("mismatch diff:\n",mis_df)
    assert match_m, "Mismatches at one NR step"
    assert match_j, "Jacobian at one NR step"

if __name__ == "__main__":
    circuit = case6_9()
    circuit.run_power_flow(flat_start=False)
    final_mis = circuit._calc_mismatch()
    buses, bus_names, ybus, angles, voltages = circuit._get_data()
    print(f'angles:\n{np.degrees(angles)}n\nbuses:\n{bus_names}\nvoltages:\n{voltages}')

