# powerflow.py
import numpy as np
import warnings
from bus import BusType
from jacobian import Jacobian  # Milestone 7

class PowerFlow:
    """
    Newton-Raphson power flow solver.

    Integrates the power mismatch vector (Milestone 6) and the Jacobian
    matrix (Milestone 7) to iteratively solve for bus voltage magnitudes
    and angles until convergence.

    Attributes:
        converged         : bool   — True if solver converged within max_iter.
        iterations        : int    — Number of iterations performed.
        mismatch_history  : list   — Max mismatch norm at each iteration.
    """

    def __init__(self):
        self.converged = False
        self.iterations = 0
        self.mismatch_history = []

    # ------------------------------------------------------------------
    # Milestone 6 helpers: power injections and mismatch vector
    # ------------------------------------------------------------------

    def _calc_Pi(self, i, ybus, angles, voltages):
        """Real power injection at bus i (Milestone 6, Eq. 2)."""
        Vi = voltages[i]
        total = 0.0
        for j in range(len(voltages)):
            dij = angles[i] - angles[j]
            total += voltages[j] * (
                ybus[i, j].real * np.cos(dij) + ybus[i, j].imag * np.sin(dij)
            )
        return Vi * total

    def _calc_Qi(self, i, ybus, angles, voltages):
        """Reactive power injection at bus i (Milestone 6, Eq. 3)."""
        Vi = voltages[i]
        total = 0.0
        for j in range(len(voltages)):
            dij = angles[i] - angles[j]
            total += voltages[j] * (
                ybus[i, j].real * np.sin(dij) - ybus[i, j].imag * np.cos(dij)
            )
        return Vi * total

    def _compute_mismatch(self, buses, ybus_np, angles, voltages):
        """
        Build the mismatch vector f = [ΔP (non-slack), ΔQ (PQ only)].

        Ordering matches the Jacobian row structure from Milestone 7:
            [ ΔP_1, ..., ΔP_{N-1},  ΔQ_1, ..., ΔQ_{NPQ} ]

        Args:
            buses    : dict[str, Bus]
            ybus_np  : np.ndarray (N x N, complex)
            angles   : np.ndarray (N,) in radians
            voltages : np.ndarray (N,) in per unit

        Returns:
            f : np.ndarray of shape (2N - 2 - NPV,)

        Note:
            Adjust 'bus.P_spec' and 'bus.Q_spec' to match the attribute names
            used in your Bus class for scheduled real and reactive power.
        """
        bus_names = list(buses.keys())
        f = []

        # ΔP for all non-slack buses
        for i, name in enumerate(bus_names):
            bus = buses[name]
            if bus.bus_type == BusType.SLACK:
                continue
            Pi_calc = self._calc_Pi(i, ybus_np, angles, voltages)
            f.append(bus.P_spec - Pi_calc)

        # ΔQ for PQ buses only
        for i, name in enumerate(bus_names):
            bus = buses[name]
            if bus.bus_type != BusType.PQ:
                continue
            Qi_calc = self._calc_Qi(i, ybus_np, angles, voltages)
            f.append(bus.Q_spec - Qi_calc)

        return np.array(f)

    # ------------------------------------------------------------------
    # Main solver
    # ------------------------------------------------------------------

    def solve(self, buses, ybus, tol=1e-3, max_iter=50):
        """
        Run the Newton-Raphson power flow solver.

        Args:
            buses    : dict[str, Bus] — ordered bus dictionary from Circuit
                       (same ordering as ybus rows/columns).
            ybus     : pd.DataFrame or np.ndarray (N x N, complex) — Y-bus matrix.
            tol      : float — convergence threshold on max(|f|). Default 1e-3.
            max_iter : int   — maximum iterations before declaring non-convergence.
                       Default 50.

        Returns:
            results : dict with keys:
                'bus_names'        — list[str], bus names in circuit order
                'voltages'         — np.ndarray (N,), final |V| in per unit
                'angles_rad'       — np.ndarray (N,), final δ in radians
                'angles_deg'       — np.ndarray (N,), final δ in degrees
                'converged'        — bool
                'iterations'       — int
                'mismatch_history' — list[float], max(|f|) per iteration
        """
        ybus_np   = ybus.values if hasattr(ybus, "values") else np.asarray(ybus)
        bus_names = list(buses.keys())
        N         = len(bus_names)

        # ---- Flat start: |V| = 1.0 pu, δ = 0.0 rad for all buses ----
        voltages = np.ones(N)
        angles   = np.zeros(N)

        # PV and slack buses hold their specified voltage magnitude
        for i, name in enumerate(bus_names):
            bus = buses[name]
            if bus.bus_type in (BusType.PV, BusType.SLACK):
                voltages[i] = bus.voltage_setpoint

        # Positional index lists (consistent with ybus ordering)
        non_slack_idx = [
            i for i, n in enumerate(bus_names)
            if buses[n].bus_type != BusType.SLACK
        ]
        pq_idx = [
            i for i, n in enumerate(bus_names)
            if buses[n].bus_type == BusType.PQ
        ]

        n_non_slack = len(non_slack_idx)

        jac = Jacobian()
        self.mismatch_history = []
        self.converged        = False
        self.iterations       = 0

        for iteration in range(max_iter):

            # Step 1 — Power mismatch vector (Milestone 6)
            f = self._compute_mismatch(buses, ybus_np, angles, voltages)

            max_mismatch = np.max(np.abs(f))
            self.mismatch_history.append(max_mismatch)

            # Step 5 — Convergence check
            if max_mismatch < tol:
                self.converged = True
                self.iterations = iteration
                print(f"Converged in {iteration} iteration(s). "
                      f"Max mismatch: {max_mismatch:.2e}")
                break

            # Step 2 — Jacobian matrix (Milestone 7)
            J = jac.calc_jacobian(buses, ybus_np, angles, voltages)

            # Step 3 — Solve linear system  J · Δx = f
            try:
                dx = np.linalg.solve(J, f)
            except np.linalg.LinAlgError:
                warnings.warn(
                    f"Singular Jacobian at iteration {iteration}. Solver aborted."
                )
                self.iterations = iteration
                break

            # Step 4 — Unpack Δx = [Δδ (non-slack) | Δ|V| (PQ only)]
            d_delta = dx[:n_non_slack]     # angle corrections (rad)
            d_volt  = dx[n_non_slack:]     # voltage magnitude corrections (pu)

            # Update δ for all non-slack buses
            for local_i, bus_idx in enumerate(non_slack_idx):
                angles[bus_idx] += d_delta[local_i]

            # Update |V| for PQ buses only
            for local_i, bus_idx in enumerate(pq_idx):
                voltages[bus_idx] += d_volt[local_i]

        else:
            # for-loop exhausted — max_iter reached without convergence
            warnings.warn(
                f"Newton-Raphson did NOT converge in {max_iter} iteration(s). "
                f"Final max mismatch: {self.mismatch_history[-1]:.6f}"
            )
            self.iterations = max_iter

        return {
            "bus_names"        : bus_names,
            "voltages"         : voltages,
            "angles_rad"       : angles,
            "angles_deg"       : np.degrees(angles),
            "converged"        : self.converged,
            "iterations"       : self.iterations,
            "mismatch_history" : self.mismatch_history,
        }
