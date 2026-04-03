# powerflow_tests.py
"""
Validation tests for the Jacobian (Milestone 7),
including mismatch (Milestone 6) and PowerFlow (Milestone 8) classes.
Test network: Glover/Sarma/Overbye 5-Bus Example 6.9
  100 MVA system base

Bus layout:
  One   — Slack  (15 kV generator bus)  → connected to Five via transformer T15
  Two   — PQ     (345 kV load bus)      → connected to Four (L42) and Five (L52)
  Three — PV     (15 kV generator bus)  → connected to Four via transformer T34
  Four  — PQ     (345 kV junction bus)  → connected to Two (L42), Five (L54), Three (T34)
  Five  — PQ     (345 kV junction bus)  → connected to One (T15), Two (L52), Four (L54)

Jacobian size: (2N - 2 - NPV) = (10 - 2 - 1) = 7×7
  Non-slack buses (δ rows/cols): Two, Three, Four, Five  → 4 buses
  PQ buses (|V| rows/cols):      Two, Four, Five         → 3 buses
"""

import unittest
from unittest.mock import patch
import numpy as np

from bus import BusType
from circuit import Circuit
from powerflow import PowerFlow


def build_circuit():
    """
    Build the 5-bus Example 6.9 circuit and attach the requested injections.

    Bus order is deterministic and used by tests: One, Two, Three, Four, Five.
    """
    circuit = Circuit("5-Bus Example 6.9")

    circuit.add_bus("One", 15.0, bus_type=BusType.Slack)
    circuit.add_bus("Two", 345.0, bus_type=BusType.PQ)
    circuit.add_bus("Three", 15.0, bus_type=BusType.PV)
    circuit.add_bus("Four", 345.0, bus_type=BusType.PQ)
    circuit.add_bus("Five", 345.0, bus_type=BusType.PQ)

    circuit.add_transmission_line("L42", "Four", "Two", r=0.009, x=0.1, b=1.72)
    circuit.add_transmission_line("L52", "Five", "Two", r=0.0045, x=0.05, b=0.88)
    circuit.add_transmission_line("L54", "Five", "Four", r=0.00225, x=0.025, b=0.44)
    circuit.add_transformer("T15", "One", "Five", r=0.0015, x=0.02)
    circuit.add_transformer("T34", "Three", "Four", r=0.00075, x=0.01)

    # Requested injections (100 MVA base):
    # Slack bus One generator: 278.3 MW -> +2.783 pu
    # Bus Two load: 800 MW / 280 MVAr -> -8.0 pu / -2.8 pu
    # Bus Three load: 80 MW / 40 MVAr -> -0.8 pu / -0.4 pu
    # Bus Three generator: 520 MW -> +5.2 pu
    circuit.add_generator("G1", "One", voltage_setpoint=1.0, mw_setpoint=0)
    circuit.add_load("LD2", "Two", mw=800.0, mvar=280.0)
    circuit.add_load("LD3", "Three", mw=80.0, mvar=40.0)
    circuit.add_generator("G3", "Three", voltage_setpoint=1.05, mw_setpoint=520.0)

    circuit.calc_ybus()
    return circuit


def setup_system():
    """Shared setup that keeps the circuit object available for all tests."""
    circuit = build_circuit()
    ybus_np = circuit.y_bus.values
    return circuit, circuit.buses, ybus_np


EXPECTED_P_SPEC = np.array([2.783, -8.0, 4.4, 0.0, 0.0])
EXPECTED_Q_SPEC = np.array([0.0, -2.8, -0.4, 0.0, 0.0])

# =============================================================================
#  REFERENCE VALUES — fill in from PowerWorld
# =============================================================================

# Ordering follows the Circuit bus dict order:
#   index 0 → One, 1 → Two, 2 → Three, 3 → Four, 4 → Five

# --- Converged angles and voltages (used as Jacobian input) ---
# Run your PowerWorld model, note the converged |V| and δ, enter them here.
CONVERGED_ANGLES_RAD = np.array([
    0.0,   # One   (slack, always 0)
    0.0,   # Two   <-- FILL IN (convert PowerWorld degrees → radians)
    0.0,   # Three <-- FILL IN
    0.0,   # Four  <-- FILL IN
    0.0,   # Five  <-- FILL IN
])

CONVERGED_VOLTAGES = np.array([
    1.00,  # One   (slack setpoint)
    1.00,  # Two   <-- FILL IN (pu)
    1.05,  # Three (PV setpoint)
    1.00,  # Four  <-- FILL IN (pu)
    1.00,  # Five  <-- FILL IN (pu)
])

# Expected Jacobian at converged operating point, shape = (7, 7).
# Rows/cols: [ΔP_Two, ΔP_Three, ΔP_Four, ΔP_Five | ΔQ_Two, ΔQ_Four, ΔQ_Five]
#            [δ_Two,  δ_Three,  δ_Four,  δ_Five  | |V|_Two, |V|_Four, |V|_Five]
EXPECTED_JACOBIAN = np.zeros((7, 7))  # <-- FILL IN (from PowerWorld Jacobian export)

# --- Mismatch vector at flat start ---
# Flat start: all δ=0, |V|=1.0 except PV (|V|=1.05) and Slack (|V|=1.0)
# Ordering: [ΔP_Two, ΔP_Three, ΔP_Four, ΔP_Five, ΔQ_Two, ΔQ_Four, ΔQ_Five]
# Verified against PowerWorld 5-bus Example 6.9 flat-start mismatch
EXPECTED_MISMATCH_FLAT = np.array([
    -8.0,      # ΔP_Two
    4.0085,    # ΔP_Three
    0.3729,    # ΔP_Four
    0.0,       # ΔP_Five
    -1.5,      # ΔQ_Two
    6.052,     # ΔQ_Four
    0.66,      # ΔQ_Five
])

# --- Mismatch vector after 1 Newton-Raphson iteration ---
# Ordering: [ΔP_Two, ΔP_Three, ΔP_Four, ΔP_Five, ΔQ_Two, ΔQ_Four, ΔQ_Five]
# Verified against PowerWorld 5-bus Example 6.9 post-iteration-1 mismatch
EXPECTED_MISMATCH_ITER1 = np.array([
    -1.7723,   # ΔP_Two
    0.8657,    # ΔP_Three
    -0.0269,   # ΔP_Four
    -0.0295,   # ΔP_Five
    -1.8595,   # ΔQ_Two
    0.2181,    # ΔQ_Four
    0.1474,    # ΔQ_Five
])

# --- Converged solution ---
EXPECTED_VOLTAGES_CONVERGED = np.array([
    1.0000,  # One   (slack)
    0.83377,     # Two   <-- FILL IN (pu)
    1.0500,  # Three (PV setpoint)
    1.01931,     # Four  <-- FILL IN (pu)
    0.97429,     # Five  <-- FILL IN (pu)
])

EXPECTED_ANGLES_DEG_CONVERGED = np.array([
    0.0,   # One   (slack)
    -22.41,   # Two   <-- FILL IN (degrees)
    -0.6,   # Three <-- FILL IN (degrees)
    -2.83,   # Four  <-- FILL IN (degrees)
    -4.55,   # Five  <-- FILL IN (degrees)
])

# Final P and Q injections at converged solution (per unit, 100 MVA base).
# Format: {bus_name: (P_calc, Q_calc)}
# Buses Two, Three, Four, Five are fully constrained by spec; One (slack) absorbs mismatch.
EXPECTED_INJECTIONS = {
    "One":   (0.0,   0.0),   # <-- FILL IN (slack bus absorbs everything)
    "Two":   (-8.0, -2.8),   # PQ: should match spec exactly at convergence
    "Three": ( 5.2,  0.0),   # PV: P matches spec; Q is free <-- FILL IN Q
    "Four":  ( 0.0,  0.0),   # PQ: should match spec
    "Five":  ( 0.0,  0.0),   # PQ: should match spec
}

# Tolerance for all np.testing comparisons (matches Milestone 8 default)
TOL = 1e-3

# =============================================================================
#  JACOBIAN TESTS
# =============================================================================

class TestJacobian(unittest.TestCase):
    """Tests for Jacobian blocks (implemented inside PowerFlow)."""

    def setUp(self):
        self.circuit, self.buses, self.ybus_np = setup_system()
        self.jac = PowerFlow()

    # ------------------------------------------------------------------
    def test_jacobian_dimension(self):
        """Jacobian must be 7×7  (2·5 − 2 − 1 PV bus = 7)."""
        J = self.jac.calc_jacobian(
            self.buses, self.ybus_np,
            CONVERGED_ANGLES_RAD, CONVERGED_VOLTAGES
        )
        self.assertEqual(J.shape, (7, 7),
                         f"Expected (7,7), got {J.shape}")

    # ------------------------------------------------------------------
    def test_submatrix_shapes(self):
        """
        J1:(4×4), J2:(4×3), J3:(3×4), J4:(3×3)
          4 non-slack buses (Two, Three, Four, Five)
          3 PQ buses        (Two, Four, Five)
        """
        self.jac.calc_jacobian(
            self.buses, self.ybus_np,
            CONVERGED_ANGLES_RAD, CONVERGED_VOLTAGES
        )
        self.assertEqual(self.jac.J1.shape, (4, 4), "J1 should be 4×4")
        self.assertEqual(self.jac.J2.shape, (4, 3), "J2 should be 4×3")
        self.assertEqual(self.jac.J3.shape, (3, 4), "J3 should be 3×4")
        self.assertEqual(self.jac.J4.shape, (3, 3), "J4 should be 3×3")

    # ------------------------------------------------------------------
    def test_jacobian_values(self):
        """Jacobian at converged operating point must match PowerWorld reference."""
        J = self.jac.calc_jacobian(
            self.buses, self.ybus_np,
            CONVERGED_ANGLES_RAD, CONVERGED_VOLTAGES
        )
        np.testing.assert_allclose(
            J, EXPECTED_JACOBIAN, atol=TOL,
            err_msg="Jacobian does not match PowerWorld reference values."
        )

    # ------------------------------------------------------------------
    def test_jacobian_mismatch_dimension_compatibility(self):
        """
        Jacobian number of rows must equal the length of the mismatch vector
        so that J · Δx = f is a valid square system.
        """
        J = self.jac.calc_jacobian(
            self.buses, self.ybus_np,
            CONVERGED_ANGLES_RAD, CONVERGED_VOLTAGES
        )
        pf   = PowerFlow()
        flat_v = np.array([b.vpu for b in self.buses.values()], dtype=float)
        flat_d = np.zeros(len(self.buses))
        f = pf._compute_mismatch(self.circuit, self.ybus_np, flat_d, flat_v)

        self.assertEqual(J.shape[0], len(f),
                         f"Jacobian rows ({J.shape[0]}) must equal mismatch length ({len(f)})")


# =============================================================================
#  POWER FLOW TESTS
# =============================================================================

class TestPowerFlow(unittest.TestCase):
    """Tests for the PowerFlow (Newton-Raphson) class on the 5-bus network."""

    def setUp(self):
        self.circuit, self.buses, self.ybus_np = setup_system()
        self.pf = PowerFlow()

    # ------------------------------------------------------------------
    def test_get_power_specs_values(self):
        """_get_power_specs must aggregate generator/load injections in bus order."""
        p_spec, q_spec = self.pf._get_power_specs(self.circuit)
        np.testing.assert_allclose(p_spec, EXPECTED_P_SPEC, atol=TOL)
        np.testing.assert_allclose(q_spec, EXPECTED_Q_SPEC, atol=TOL)

    # ------------------------------------------------------------------
    def test_get_power_specs_shape_matches_bus_count(self):
        """P/Q spec vectors must be length N where N is circuit bus count."""
        p_spec, q_spec = self.pf._get_power_specs(self.circuit)
        n = len(self.buses)
        self.assertEqual(len(p_spec), n)
        self.assertEqual(len(q_spec), n)

    # ------------------------------------------------------------------
    def test_mismatch_vector_length(self):
        """Mismatch vector must have length 7 (4 ΔP entries + 3 ΔQ entries)."""
        flat_v = np.array([b.vpu for b in self.buses.values()], dtype=float)
        flat_d = np.zeros(len(self.buses))
        f = self.pf._compute_mismatch(self.circuit, self.ybus_np, flat_d, flat_v)
        self.assertEqual(len(f), 7,
                         f"Expected mismatch vector of length 7, got {len(f)}")

    # ------------------------------------------------------------------
    def test_mismatch_ordering(self):
        """
        Prove ordering by perturbing one spec entry at a time and checking
        exactly which mismatch index changes.

        This avoids self-referential label checks and validates positional mapping
        of [ΔP non-slack ... | ΔQ PQ-only ...] directly from behavior.
        """
        flat_v = np.array([b.vpu for b in self.buses.values()], dtype=float)
        flat_d = np.zeros(len(self.buses), dtype=float)

        p0, q0 = self.pf._get_power_specs(self.circuit)
        f0 = self.pf._compute_mismatch(self.circuit, self.ybus_np, flat_d, flat_v)

        bus_names = list(self.buses.keys())
        bus_types = np.array([b.bus_type for b in self.buses.values()], dtype=object)
        non_slack_idx = np.flatnonzero(bus_types != BusType.Slack)
        pq_idx = np.flatnonzero(bus_types == BusType.PQ)

        eps = 1e-4

        # P-block ordering: index k corresponds to non_slack_idx[k]
        for k, bus_i in enumerate(non_slack_idx):
            p_test = p0.copy()
            q_test = q0.copy()
            p_test[bus_i] += eps

            with patch.object(self.pf, "_get_power_specs", return_value=(p_test, q_test)):
                f = self.pf._compute_mismatch(self.circuit, self.ybus_np, flat_d, flat_v)

            df = f - f0
            moved = np.where(np.abs(df) > 1e-10)[0]

            self.assertEqual(
                len(moved), 1,
                msg=f"Expected one changed mismatch entry for P perturbation at bus '{bus_names[bus_i]}'"
            )
            self.assertEqual(
                moved[0], k,
                msg=f"Wrong ΔP ordering for bus '{bus_names[bus_i]}': expected index {k}, got {moved[0]}"
            )
            self.assertAlmostEqual(df[k], eps, delta=1e-10)

        # Q-block ordering: index (offset + k) corresponds to pq_idx[k]
        offset = len(non_slack_idx)
        for k, bus_i in enumerate(pq_idx):
            p_test = p0.copy()
            q_test = q0.copy()
            q_test[bus_i] += eps

            with patch.object(self.pf, "_get_power_specs", return_value=(p_test, q_test)):
                f = self.pf._compute_mismatch(self.circuit, self.ybus_np, flat_d, flat_v)

            df = f - f0
            moved = np.where(np.abs(df) > 1e-10)[0]

            self.assertEqual(
                len(moved), 1,
                msg=f"Expected one changed mismatch entry for Q perturbation at bus '{bus_names[bus_i]}'"
            )
            expected_idx = offset + k
            self.assertEqual(
                moved[0], expected_idx,
                msg=(
                    f"Wrong ΔQ ordering for bus '{bus_names[bus_i]}': "
                    f"expected index {expected_idx}, got {moved[0]}"
                )
            )
            self.assertAlmostEqual(df[expected_idx], eps, delta=1e-10)

    # ------------------------------------------------------------------
    def test_mismatch_flat_start_values(self):
        """Full flat-start mismatch vector must match reference (fill in from PowerWorld)."""
        flat_v = np.array([b.vpu for b in self.buses.values()], dtype=float)
        flat_d = np.zeros(len(self.buses))

        f = self.pf._compute_mismatch(self.circuit, self.ybus_np, flat_d, flat_v)
        np.testing.assert_allclose(
            f, EXPECTED_MISMATCH_FLAT, atol=TOL,
            err_msg="Flat-start mismatch vector does not match reference."
        )
    
    # ------------------------------------------------------------------
    def test_mismatch_angle_volt_from_powerworld(self):
        """Full flat-start mismatch vector must match reference (fill in from PowerWorld)."""
        flat_v = np.array([1,.987,1.05,1.3314,1.01057], dtype=float)
        degrees_powerworld = np.array([0, -14.66, 0.16, -1.63, -3.21], dtype=float)
        radians_powerworld = np.deg2rad(degrees_powerworld)
        flat_d = np.array(radians_powerworld,dtype=float)

        f = self.pf._compute_mismatch(self.circuit, self.ybus_np, flat_d, flat_v)
        np.testing.assert_allclose(
            f, EXPECTED_MISMATCH_ITER1, atol=TOL,
            err_msg="Flat-start mismatch vector does not match reference."
        )


    # ------------------------------------------------------------------
    def test_calc_power_injections_flat_start_matches_powerworld_derived(self):
        """
        Validate selected flat-start P/Q injections derived from PowerWorld mismatch:
          mismatch = spec - calc  =>  calc = spec - mismatch
        """
        flat_v = np.array([b.vpu for b in self.buses.values()], dtype=float)
        flat_d = np.zeros(len(self.buses), dtype=float)
        p_calc, q_calc = self.pf._calc_power_injections(self.ybus_np, flat_d, flat_v)
        p_spec, q_spec = self.pf._get_power_specs(self.circuit)

        # Non-slack P entries are directly recoverable from the reference mismatch.
        p_calc_ref = np.array([
            p_spec[1] - EXPECTED_MISMATCH_FLAT[0],  # Bus Two
            p_spec[2] - EXPECTED_MISMATCH_FLAT[1],  # Bus Three
            p_spec[3] - EXPECTED_MISMATCH_FLAT[2],  # Bus Four
            p_spec[4] - EXPECTED_MISMATCH_FLAT[3],  # Bus Five
        ])
        np.testing.assert_allclose(p_calc[1:], p_calc_ref, atol=1e-3)

        # PQ Q entries are also directly recoverable from the reference mismatch.
        q_calc_ref = np.array([
            q_spec[1] - EXPECTED_MISMATCH_FLAT[4],  # Bus Two
            q_spec[3] - EXPECTED_MISMATCH_FLAT[5],  # Bus Four
            q_spec[4] - EXPECTED_MISMATCH_FLAT[6],  # Bus Five
        ])
        np.testing.assert_allclose(np.array([q_calc[1], q_calc[3], q_calc[4]]), q_calc_ref, atol=1e-3)

    # ------------------------------------------------------------------
    def test_compute_mismatch_equals_specs_minus_calculated_injections(self):
        """_compute_mismatch must exactly assemble [Pspec-Pcalc | Qspec-Qcalc] with proper indexing."""
        flat_v = np.array([b.vpu for b in self.buses.values()], dtype=float)
        flat_d = np.zeros(len(self.buses), dtype=float)

        p_spec, q_spec = self.pf._get_power_specs(self.circuit)
        p_calc, q_calc = self.pf._calc_power_injections(self.ybus_np, flat_d, flat_v)
        f = self.pf._compute_mismatch(self.circuit, self.ybus_np, flat_d, flat_v)

        bus_types = np.array([b.bus_type for b in self.buses.values()], dtype=object)
        non_slack_idx = np.flatnonzero(bus_types != BusType.Slack)
        pq_idx = np.flatnonzero(bus_types == BusType.PQ)

        expected = np.concatenate([
            p_spec[non_slack_idx] - p_calc[non_slack_idx],
            q_spec[pq_idx] - q_calc[pq_idx],
        ])
        np.testing.assert_allclose(f, expected, atol=1e-10)

    # ------------------------------------------------------------------
    def test_calc_jacobian_matches_finite_difference_mismatch(self):
        """
        Jacobian should match finite-difference derivative of mismatch
        around flat-start state.
        """
        angles = np.zeros(len(self.buses), dtype=float)
        voltages = np.array([b.vpu for b in self.buses.values()], dtype=float)

        J = self.pf.calc_jacobian(self.buses, self.ybus_np, angles, voltages)

        bus_types = np.array([b.bus_type for b in self.buses.values()], dtype=object)
        non_slack_idx = np.flatnonzero(bus_types != BusType.Slack)
        pq_idx = np.flatnonzero(bus_types == BusType.PQ)

        eps = 1e-6
        J_fd = np.zeros_like(J)

        # Columns for delta(non-slack)
        for col, i in enumerate(non_slack_idx):
            a_plus = angles.copy()
            a_minus = angles.copy()
            a_plus[i] += eps
            a_minus[i] -= eps
            f_plus = self.pf._compute_mismatch(self.circuit, self.ybus_np, a_plus, voltages)
            f_minus = self.pf._compute_mismatch(self.circuit, self.ybus_np, a_minus, voltages)
            J_fd[:, col] = (f_plus - f_minus) / (2.0 * eps)

        # Columns for |V|(PQ)
        offset = len(non_slack_idx)
        for local_col, i in enumerate(pq_idx):
            v_plus = voltages.copy()
            v_minus = voltages.copy()
            v_plus[i] += eps
            v_minus[i] -= eps
            f_plus = self.pf._compute_mismatch(self.circuit, self.ybus_np, angles, v_plus)
            f_minus = self.pf._compute_mismatch(self.circuit, self.ybus_np, angles, v_minus)
            J_fd[:, offset + local_col] = (f_plus - f_minus) / (2.0 * eps)

        # Code Jacobian is built from derivatives of calculated injections,
        # while mismatch is f = spec - calc. Therefore: J ~= -(df/dx).
        np.testing.assert_allclose(
            J, -J_fd, atol=1e-3,
            err_msg="Jacobian sign/magnitude does not match finite-difference sensitivity at flat-start."
        )

    # ------------------------------------------------------------------
    def test_solver_converges(self):
        """Newton-Raphson must converge within 50 iterations for this well-conditioned system."""
        results = self.pf.solve(self.circuit, self.ybus_np, tol=TOL, max_iter=50)
        self.assertTrue(results["converged"],
                        f"Solver did not converge. "
                        f"Iterations: {self.pf.iterations}, "
                        f"Final mismatch: {self.pf.mismatch_history[-1]:.6f}")

    # ------------------------------------------------------------------
    def test_converged_voltages(self):
        """Final |V| at each bus must match PowerWorld converged values."""
        results = self.pf.solve(self.circuit, self.ybus_np, tol=TOL, max_iter=50)
        np.testing.assert_allclose(
            results["voltages"], EXPECTED_VOLTAGES_CONVERGED, atol=TOL,
            err_msg="Converged bus voltages do not match PowerWorld reference."
        )

    # ------------------------------------------------------------------
    def test_converged_angles(self):
        """Final δ (degrees) at each bus must match PowerWorld converged values."""
        results = self.pf.solve(self.circuit, self.ybus_np, tol=TOL, max_iter=50)
        np.testing.assert_allclose(
            results["angles_deg"], EXPECTED_ANGLES_DEG_CONVERGED, atol=0.01,
            err_msg="Converged bus angles do not match PowerWorld reference."
        )

    # ------------------------------------------------------------------
    def test_power_injections_at_convergence(self):
        """Calculated P and Q at each bus after convergence must match expected injections."""
        results  = self.pf.solve(self.circuit, self.ybus_np, tol=TOL, max_iter=50)
        voltages = results["voltages"]
        angles   = results["angles_rad"]
        bus_names = list(self.buses.keys())

        for i, name in enumerate(bus_names):
            Pi_calc = self.pf._calc_Pi(i, self.ybus_np, angles, voltages)
            Qi_calc = self.pf._calc_Qi(i, self.ybus_np, angles, voltages)
            P_ref, Q_ref = EXPECTED_INJECTIONS[name]

            self.assertAlmostEqual(Pi_calc, P_ref, delta=TOL,
                msg=f"{name}: P={Pi_calc:.4f} pu, expected {P_ref:.4f} pu")
            self.assertAlmostEqual(Qi_calc, Q_ref, delta=TOL,
                msg=f"{name}: Q={Qi_calc:.4f} pu, expected {Q_ref:.4f} pu")

    # ------------------------------------------------------------------
    def test_slack_bus_fixed(self):
        """Bus 'One' (slack) must remain at |V|=1.0 pu and δ=0° after solve."""
        results   = self.pf.solve(self.circuit, self.ybus_np, tol=TOL, max_iter=50)
        bus_names = results["bus_names"]
        idx       = bus_names.index("One")

        self.assertAlmostEqual(results["voltages"][idx], 1.0, delta=TOL,
                               msg="Slack bus voltage must stay at 1.0 pu")
        self.assertAlmostEqual(results["angles_deg"][idx], 0.0, delta=TOL,
                               msg="Slack bus angle must stay at 0°")

    # ------------------------------------------------------------------
    def test_pv_bus_voltage_fixed(self):
        """Bus 'Three' (PV) must keep |V|=1.05 pu throughout the iteration."""
        results   = self.pf.solve(self.circuit, self.ybus_np, tol=TOL, max_iter=50)
        bus_names = results["bus_names"]
        idx       = bus_names.index("Three")

        self.assertAlmostEqual(results["voltages"][idx], 1.05, delta=TOL,
                               msg="PV bus 'Three' voltage must remain at 1.05 pu")

    # ------------------------------------------------------------------
    def test_pq_bus_specs_satisfied(self):
        """
        At convergence, computed P (and Q) at PQ buses Two, Four, Five
        must equal their scheduled values within tolerance.
        """
        results   = self.pf.solve(self.circuit, self.ybus_np, tol=TOL, max_iter=50)
        voltages  = results["voltages"]
        angles    = results["angles_rad"]
        bus_names = list(self.buses.keys())

        pq_specs = {
            "Two":  (-8.0, -2.8),
            "Four": ( 0.0,  0.0),
            "Five": ( 0.0,  0.0),
        }
        for name, (P_ref, Q_ref) in pq_specs.items():
            i       = bus_names.index(name)
            Pi_calc = self.pf._calc_Pi(i, self.ybus_np, angles, voltages)
            Qi_calc = self.pf._calc_Qi(i, self.ybus_np, angles, voltages)
            self.assertAlmostEqual(Pi_calc, P_ref, delta=TOL,
                msg=f"PQ bus '{name}' P not at spec: got {Pi_calc:.4f}, expected {P_ref}")
            self.assertAlmostEqual(Qi_calc, Q_ref, delta=TOL,
                msg=f"PQ bus '{name}' Q not at spec: got {Qi_calc:.4f}, expected {Q_ref}")

    # ------------------------------------------------------------------
    def test_flat_start_mismatch_matches_powerworld(self):
        """Validate flat-start mismatch vector matches PowerWorld reference."""
        flat_v = np.array([b.vpu for b in self.buses.values()], dtype=float)
        flat_d = np.zeros(len(self.buses))
        f = self.pf._compute_mismatch(self.circuit, self.ybus_np, flat_d, flat_v)
        np.testing.assert_allclose(
            f, EXPECTED_MISMATCH_FLAT, atol=1e-2,
            err_msg="Flat-start mismatch does not match PowerWorld reference."
        )

    # ------------------------------------------------------------------
    def test_single_iteration_mismatch_matches_powerworld(self):
        """
        Validate post-iteration-1 mismatch using explicit NR step ordering:
        mismatch -> Jacobian -> solve dx -> update state -> mismatch.
        """
        # Flat-start state: delta=0 for all, |V|=1 except PV/slack setpoints.
        angles = np.zeros(len(self.buses), dtype=float)
        voltages = np.array([b.vpu for b in self.buses.values()], dtype=float)

        # 1) Compute mismatch at current state
        f0 = self.pf._compute_mismatch(self.circuit, self.ybus_np, angles, voltages)

        # 2) Build Jacobian at current state
        J0 = self.pf.calc_jacobian(self.buses, self.ybus_np, angles, voltages)

        # 3) Solve for state correction dx
        dx = np.linalg.solve(J0, f0)

        # 4) Unpack and apply corrections
        bus_types = np.array([b.bus_type for b in self.buses.values()], dtype=object)
        non_slack_idx = np.flatnonzero(bus_types != BusType.Slack)
        pq_idx = np.flatnonzero(bus_types == BusType.PQ)
        n_non_slack = len(non_slack_idx)

        d_delta = dx[:n_non_slack]
        d_volt = dx[n_non_slack:]

        for local_i, bus_idx in enumerate(non_slack_idx):
            angles[bus_idx] += d_delta[local_i]

        for local_i, bus_idx in enumerate(pq_idx):
            voltages[bus_idx] += d_volt[local_i]

        # 5) Compute mismatch at post-iteration-1 state
        f_iter1 = self.pf._compute_mismatch(self.circuit, self.ybus_np, angles, voltages)

        np.testing.assert_allclose(
            f_iter1, EXPECTED_MISMATCH_ITER1, atol=1e-2,
            err_msg="Post-iteration-1 mismatch does not match PowerWorld reference."
        )

    # ------------------------------------------------------------------
    def test_pv_bus_p_spec_satisfied(self):
        """At convergence, real power injection at PV bus 'Three' must equal 5.2 pu."""
        results   = self.pf.solve(self.circuit, self.ybus_np, tol=TOL, max_iter=50)
        bus_names = list(self.buses.keys())
        idx       = bus_names.index("Three")
        Pi_calc   = self.pf._calc_Pi(
            idx, self.ybus_np, results["angles_rad"], results["voltages"]
        )
        self.assertAlmostEqual(Pi_calc, 5.2, delta=TOL,
                               msg=f"Bus 'Three' P injection {Pi_calc:.4f} != 5.2 pu")


# =============================================================================
#  ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
