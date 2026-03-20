# powerflow.py
import numpy as np
import warnings
from bus import BusType

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
        self.J1 = self.J2 = self.J3 = self.J4 = self.J = None

    # ------------------------------------------------------------------
    # Milestone 6 helpers: power injections and mismatch vector
    # ------------------------------------------------------------------

    def _get_voltage_setpoints(self, buses):
        return np.array([
            float(getattr(bus, "voltage_setpoint", getattr(bus, "vpu", 1.0)))
            for bus in buses.values()
        ], dtype=float)

    def _get_power_specs(self, buses):
        p_spec = np.array([
            float(getattr(bus, "P_spec", getattr(bus, "p_spec", 0.0)))
            for bus in buses.values()
        ], dtype=float)
        q_spec = np.array([
            float(getattr(bus, "Q_spec", getattr(bus, "q_spec", 0.0)))
            for bus in buses.values()
        ], dtype=float)
        return p_spec, q_spec

    def _calc_power_injections(self, ybus_np, angles, voltages):
        """Vectorized real and reactive power injections for all buses."""
        G = ybus_np.real
        B = ybus_np.imag
        dtheta = angles[:, None] - angles[None, :]
        cos_d = np.cos(dtheta)
        sin_d = np.sin(dtheta)
        VV = voltages[:, None] * voltages[None, :]

        P = np.sum(VV * (G * cos_d + B * sin_d), axis=1)
        Q = np.sum(VV * (G * sin_d - B * cos_d), axis=1)
        return P, Q

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
        bus_types = np.array([bus.bus_type for bus in buses.values()], dtype=object)
        ns = np.flatnonzero(bus_types != BusType.Slack)
        pq = np.flatnonzero(bus_types == BusType.PQ)
        p_spec, q_spec = self._get_power_specs(buses)
        P, Q = self._calc_power_injections(ybus_np, angles, voltages)

        return np.concatenate([p_spec[ns] - P[ns], q_spec[pq] - Q[pq]])

    def calc_jacobian(self, buses, ybus, angles, voltages):
        """Build the full Jacobian matrix for a Newton-Raphson iteration."""
        ybus_np = ybus.values if hasattr(ybus, "values") else np.asarray(ybus)
        bus_types = np.array([bus.bus_type for bus in buses.values()], dtype=object)
        ns = np.flatnonzero(bus_types != BusType.Slack)
        pq = np.flatnonzero(bus_types == BusType.PQ)

        G = ybus_np.real
        B = ybus_np.imag
        dtheta = angles[:, None] - angles[None, :]
        cos_d = np.cos(dtheta)
        sin_d = np.sin(dtheta)
        VV = voltages[:, None] * voltages[None, :]
        voltage_sq = voltages ** 2
        P, Q = self._calc_power_injections(ybus_np, angles, voltages)
        p_over_v = np.divide(
            P,
            voltages,
            out=np.zeros_like(voltages),
            where=voltages != 0,
        )
        q_over_v = np.divide(
            Q,
            voltages,
            out=np.zeros_like(voltages),
            where=voltages != 0,
        )

        H = VV * (G * sin_d - B * cos_d)
        np.fill_diagonal(H, -Q - np.diagonal(B) * voltage_sq)
        self.J1 = H[np.ix_(ns, ns)]

        N = voltages[:, None] * (G * cos_d + B * sin_d)
        np.fill_diagonal(N, p_over_v + np.diagonal(G) * voltages)
        self.J2 = N[np.ix_(ns, pq)]

        Jm = -VV * (G * cos_d + B * sin_d)
        np.fill_diagonal(Jm, P - np.diagonal(G) * voltage_sq)
        self.J3 = Jm[np.ix_(pq, ns)]

        L = voltages[:, None] * (G * sin_d - B * cos_d)
        np.fill_diagonal(L, q_over_v - np.diagonal(B) * voltages)
        self.J4 = L[np.ix_(pq, pq)]

        self.J = np.block([
            [self.J1, self.J2],
            [self.J3, self.J4],
        ])
        return self.J

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
        N = len(bus_names)
        bus_types = np.array([bus.bus_type for bus in buses.values()], dtype=object)
        voltage_setpoints = self._get_voltage_setpoints(buses)

        # ---- Flat start: |V| = 1.0 pu, δ = 0.0 rad for all buses ----
        voltages = np.ones(N)
        angles = np.zeros(N)

        # PV and slack buses hold their specified voltage magnitude
        hold_voltage_mask = (bus_types == BusType.PV) | (bus_types == BusType.Slack)
        voltages[hold_voltage_mask] = voltage_setpoints[hold_voltage_mask]

        # Positional index lists (consistent with ybus ordering)
        non_slack_idx = np.flatnonzero(bus_types != BusType.Slack)
        pq_idx = np.flatnonzero(bus_types == BusType.PQ)

        n_non_slack = len(non_slack_idx)

        self.mismatch_history = []
        self.converged = False
        self.iterations = 0

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
            J = self.calc_jacobian(buses, ybus_np, angles, voltages)

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
