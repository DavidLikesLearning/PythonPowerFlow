# jacobian.py
import numpy as np
from bus import BusType


class Jacobian:
    """
    Jacobian matrix for the Newton-Raphson power flow solver.

    Constructs the (2N - 2 - NPV) x (2N - 2 - NPV) Jacobian from four
    sub-matrices based on partial derivatives of the power injection equations:

        J = | J1  J2 |  =  | dP/d_delta   dP/d|V| |
            | J3  J4 |     | dQ/d_delta   dQ/d|V| |

    Rows/columns corresponding to the slack bus are excluded entirely.
    Rows/columns corresponding to PV buses are excluded from J3, J4 (no dQ).
    """

    def __init__(self):
        self.J1 = None  # dP/d_delta  — shape (N-1, N-1)
        self.J2 = None  # dP/d|V|     — shape (N-1, NPQ)
        self.J3 = None  # dQ/d_delta  — shape (NPQ,  N-1)
        self.J4 = None  # dQ/d|V|     — shape (NPQ,  NPQ)
        self.J  = None  # Full Jacobian

    # ------------------------------------------------------------------
    # Private helpers: compute Pi and Qi at bus i using current V, delta
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Sub-matrix calculations
    # ------------------------------------------------------------------

    def _calc_J1(self, non_slack_idx, ybus, angles, voltages):
        """
        J1 = dP/d_delta, shape (N-1, N-1).

        Off-diagonal (i != k): |Vi||Vk| * (Gik*sin(dik) - Bik*cos(dik))
        Diagonal     (i == k): -Qi - Bii*|Vi|^2
        """
        n = len(non_slack_idx)
        J1 = np.zeros((n, n))
        for row, i in enumerate(non_slack_idx):
            Vi  = voltages[i]
            Bii = ybus[i, i].imag
            Qi  = self._calc_Qi(i, ybus, angles, voltages)
            for col, k in enumerate(non_slack_idx):
                if i == k:
                    J1[row, col] = -Qi - Bii * Vi**2
                else:
                    Vk  = voltages[k]
                    dik = angles[i] - angles[k]
                    Gik = ybus[i, k].real
                    Bik = ybus[i, k].imag
                    J1[row, col] = Vi * Vk * (Gik * np.sin(dik) - Bik * np.cos(dik))
        return J1

    def _calc_J2(self, non_slack_idx, pq_idx, ybus, angles, voltages):
        """
        J2 = dP/d|V|, shape (N-1, NPQ).

        Off-diagonal (i != k): |Vi| * (Gik*cos(dik) + Bik*sin(dik))
        Diagonal     (i == k): Pi/|Vi| + Gii*|Vi|
        """
        J2 = np.zeros((len(non_slack_idx), len(pq_idx)))
        for row, i in enumerate(non_slack_idx):
            Vi  = voltages[i]
            Gii = ybus[i, i].real
            Pi  = self._calc_Pi(i, ybus, angles, voltages)
            for col, k in enumerate(pq_idx):
                if i == k:
                    J2[row, col] = Pi / Vi + Gii * Vi
                else:
                    dik = angles[i] - angles[k]
                    Gik = ybus[i, k].real
                    Bik = ybus[i, k].imag
                    J2[row, col] = Vi * (Gik * np.cos(dik) + Bik * np.sin(dik))
        return J2

    def _calc_J3(self, pq_idx, non_slack_idx, ybus, angles, voltages):
        """
        J3 = dQ/d_delta, shape (NPQ, N-1).

        Off-diagonal (i != k): -|Vi||Vk| * (Gik*cos(dik) + Bik*sin(dik))
        Diagonal     (i == k):  Pi - Gii*|Vi|^2
        """
        J3 = np.zeros((len(pq_idx), len(non_slack_idx)))
        for row, i in enumerate(pq_idx):
            Vi  = voltages[i]
            Gii = ybus[i, i].real
            Pi  = self._calc_Pi(i, ybus, angles, voltages)
            for col, k in enumerate(non_slack_idx):
                if i == k:
                    J3[row, col] = Pi - Gii * Vi**2
                else:
                    Vk  = voltages[k]
                    dik = angles[i] - angles[k]
                    Gik = ybus[i, k].real
                    Bik = ybus[i, k].imag
                    J3[row, col] = -Vi * Vk * (Gik * np.cos(dik) + Bik * np.sin(dik))
        return J3

    def _calc_J4(self, pq_idx, ybus, angles, voltages):
        """
        J4 = dQ/d|V|, shape (NPQ, NPQ).

        Off-diagonal (i != k): |Vi| * (Gik*sin(dik) - Bik*cos(dik))
        Diagonal     (i == k): Qi/|Vi| - Bii*|Vi|
        """
        n = len(pq_idx)
        J4 = np.zeros((n, n))
        for row, i in enumerate(pq_idx):
            Vi  = voltages[i]
            Bii = ybus[i, i].imag
            Qi  = self._calc_Qi(i, ybus, angles, voltages)
            for col, k in enumerate(pq_idx):
                if i == k:
                    J4[row, col] = Qi / Vi - Bii * Vi
                else:
                    dik = angles[i] - angles[k]
                    Gik = ybus[i, k].real
                    Bik = ybus[i, k].imag
                    J4[row, col] = Vi * (Gik * np.sin(dik) - Bik * np.cos(dik))
        return J4

    # ------------------------------------------------------------------
    # Public method
    # ------------------------------------------------------------------

    def calc_jacobian(self, buses, ybus, angles, voltages):
        """
        Build the full Jacobian matrix for a Newton-Raphson iteration.

        The matrix dimension is (2N - 2 - NPV) x (2N - 2 - NPV), matching
        the length of the power mismatch vector from Milestone 6.

        Args:
            buses    : dict[str, Bus] — ordered bus dictionary from Circuit
                       (same ordering as ybus rows/columns).
            ybus     : pd.DataFrame or np.ndarray (N x N, complex) — admittance matrix.
            angles   : np.ndarray (N,) — current voltage angles in radians.
            voltages : np.ndarray (N,) — current voltage magnitudes in per unit.

        Returns:
            J : np.ndarray of shape (2N-2-NPV, 2N-2-NPV) — full Jacobian matrix.
        """
        # Convert ybus to raw numpy for indexing
        ybus_np = ybus.values if hasattr(ybus, "values") else np.asarray(ybus)

        bus_names = list(buses.keys())

        # Bus index lists (positional, matching ybus row/col order)
        non_slack_idx = [
            i for i, name in enumerate(bus_names)
            if buses[name].bus_type != BusType.SLACK
        ]
        pq_idx = [
            i for i, name in enumerate(bus_names)
            if buses[name].bus_type == BusType.PQ
        ]

        # Compute the four sub-matrices
        self.J1 = self._calc_J1(non_slack_idx, ybus_np, angles, voltages)
        self.J2 = self._calc_J2(non_slack_idx, pq_idx,  ybus_np, angles, voltages)
        self.J3 = self._calc_J3(pq_idx, non_slack_idx,  ybus_np, angles, voltages)
        self.J4 = self._calc_J4(pq_idx,                 ybus_np, angles, voltages)

        # Assemble full Jacobian using block structure
        self.J = np.block([
            [self.J1, self.J2],
            [self.J3, self.J4]
        ])
        return self.J
