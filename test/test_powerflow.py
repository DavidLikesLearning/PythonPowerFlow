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
import warnings
import numpy as np

from bus import Bus, BusType
from circuit import Circuit
from jacobian import Jacobian
from powerflow import PowerFlow


def build_circuit():
    """
    Construct the Glover/Sarma 5-Bus Example 6.9 circuit.
    NOTE: Bus 'One' is corrected to BusType.SLACK (it is the swing bus).
    """
    circuit = Circuit("5-Bus Example 6.9")

    # Bus 'One' is the SLACK bus (swing bus) in this textbook example.
    circuit.add_bus("One",   15.0,  bus_type=BusType.Slack)  # corrected from PQ
    circuit.add_bus("Two",   345.0, bus_type=BusType.PQ)
    circuit.add_bus("Three", 15.0,  bus_type=BusType.PV)
    circuit.add_bus("Four",  345.0, bus_type=BusType.PQ)
    circuit.add_bus("Five",  345.0, bus_type=BusType.PQ)

    circuit.add_transmission_line("L42", "Four", "Two",  r=0.009,   x=0.1,  b=1.72)
    circuit.add_transmission_line("L52", "Five", "Two",  r=0.0045,  x=0.05, b=0.88)
    circuit.add_transmission_line("L54", "Five", "Four", r=0.00225, x=0.025, b=0.44)
    circuit.add_transformer("T15", "One",   "Five", r=0.0015,  x=0.02)
    circuit.add_transformer("T34", "Three", "Four", r=0.00075, x=0.01)

    return circuit

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
EXPECTED_MISMATCH_FLAT = np.array([
    -8.0,   # ΔP_Two  : P_spec - P_calc (at flat start, P_calc ≈ 0 for pure reactive ybus)
    5.2,    # ΔP_Three
    0.0,    # ΔP_Four
    0.0,    # ΔP_Five
    -2.8,   # ΔQ_Two
    0.0,    # ΔQ_Four
    0.0,    # ΔQ_Five
    # NOTE: At a true flat start with no shunt conductance, all P_calc and Q_calc
    # contributions may be nonzero due to shunt susceptance (b terms).
    # Replace all values above with your computed flat-start mismatch. <-- FILL IN
])

# --- Converged solution ---
EXPECTED_VOLTAGES_CONVERGED = np.array([
    1.0000,  # One   (slack)
    0.0,     # Two   <-- FILL IN (pu)
    1.0500,  # Three (PV setpoint)
    0.0,     # Four  <-- FILL IN (pu)
    0.0,     # Five  <-- FILL IN (pu)
])

EXPECTED_ANGLES_DEG_CONVERGED = np.array([
    0.0,   # One   (slack)
    0.0,   # Two   <-- FILL IN (degrees)
    0.0,   # Three <-- FILL IN (degrees)
    0.0,   # Four  <-- FILL IN (degrees)
    0.0,   # Five  <-- FILL IN (degrees)
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
    """Tests for the Jacobian class (Milestone 7) on the 5-bus network."""

    def setUp(self):
        self.buses, self.ybus_np = setup_system()
        self.jac = Jacobian()

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
        flat_v = np.array([b.voltage_setpoint for b in self.buses.values()])
        flat_d = np.zeros(len(self.buses))
        f = pf._compute_mismatch(self.buses, self.ybus_np, flat_d, flat_v)

        self.assertEqual(J.shape[0], len(f),
                         f"Jacobian rows ({J.shape[0]}) must equal mismatch length ({len(f)})")


# =============================================================================
#  POWER FLOW TESTS
# =============================================================================

class TestPowerFlow(unittest.TestCase):
    """Tests for the PowerFlow (Newton-Raphson) class (Milestone 8) on the 5-bus network."""

    # ------------------------------------------------------------------
    def test_mismatch_vector_length(self):
        """Mismatch vector must have length 7 (4 ΔP entries + 3 ΔQ entries)."""
        flat_v = np.array([b.voltage_setpoint for b in self.buses.values()])
        flat_d = np.zeros(len(self.buses))
        f = self.pf._compute_mismatch(self.buses, self.ybus_np, flat_d, flat_v)
        self.assertEqual(len(f), 7,
                         f"Expected mismatch vector of length 7, got {len(f)}")

    # ------------------------------------------------------------------
    def test_mismatch_ordering(self):
        """
        Mismatch vector must be ordered: [ΔP non-slack ... | ΔQ PQ-only ...]
        Verify bus names appear in the correct half by checking known zero entries.
        At flat start, all ΔP for junction buses (Four, Five) should match their P_spec=0.
        """
        flat_v = np.array([b.voltage_setpoint for b in self.buses.values()])
        flat_d = np.zeros(len(self.buses))
        f = self.pf._compute_mismatch(self.buses, self.ybus_np, flat_d, flat_v)

        # ΔP_Four is index 2, ΔP_Five is index 3  (non-slack order: Two, Three, Four, Five)
        # At flat start the real power injection through a lossless reactive network
        # is zero, so ΔP = P_spec - 0 = P_spec for Four and Five (both 0.0).
        self.assertAlmostEqual(f[2], 0.0, delta=TOL,
                               msg="ΔP_Four at flat start should be 0.0 (P_spec=0)")
        self.assertAlmostEqual(f[3], 0.0, delta=TOL,
                               msg="ΔP_Five at flat start should be 0.0 (P_spec=0)")

    # ------------------------------------------------------------------
    def test_mismatch_flat_start_values(self):
        """Full flat-start mismatch vector must match reference (fill in from PowerWorld)."""
        flat_v = np.array([b.voltage_setpoint for b in self.buses.values()])
        flat_d = np.zeros(len(self.buses))
        f = self.pf._compute_mismatch(self.buses, self.ybus_np, flat_d, flat_v)
        np.testing.assert_allclose(
            f, EXPECTED_MISMATCH_FLAT, atol=TOL,
            err_msg="Flat-start mismatch vector does not match reference."
        )

    # ------------------------------------------------------------------
    def test_solver_converges(self):
        """Newton-Raphson must converge within 50 iterations for this well-conditioned system."""
        results = self.pf.solve(self.buses, self.ybus_np, tol=TOL, max_iter=50)
        self.assertTrue(results["converged"],
                        f"Solver did not converge. "
                        f"Iterations: {self.pf.iterations}, "
                        f"Final mismatch: {self.pf.mismatch_history[-1]:.6f}")

    # ------------------------------------------------------------------
    def test_converged_voltages(self):
        """Final |V| at each bus must match PowerWorld converged values."""
        results = self.pf.solve(self.buses, self.ybus_np, tol=TOL, max_iter=50)
        np.testing.assert_allclose(
            results["voltages"], EXPECTED_VOLTAGES_CONVERGED, atol=TOL,
            err_msg="Converged bus voltages do not match PowerWorld reference."
        )

    # ------------------------------------------------------------------
    def test_converged_angles(self):
        """Final δ (degrees) at each bus must match PowerWorld converged values."""
        results = self.pf.solve(self.buses, self.ybus_np, tol=TOL, max_iter=50)
        np.testing.assert_allclose(
            results["angles_deg"], EXPECTED_ANGLES_DEG_CONVERGED, atol=TOL,
            err_msg="Converged bus angles do not match PowerWorld reference."
        )

    # ------------------------------------------------------------------
    def test_power_injections_at_convergence(self):
        """Calculated P and Q at each bus after convergence must match expected injections."""
        results  = self.pf.solve(self.buses, self.ybus_np, tol=TOL, max_iter=50)
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
        results   = self.pf.solve(self.buses, self.ybus_np, tol=TOL, max_iter=50)
        bus_names = results["bus_names"]
        idx       = bus_names.index("One")

        self.assertAlmostEqual(results["voltages"][idx], 1.0, delta=TOL,
                               msg="Slack bus voltage must stay at 1.0 pu")
        self.assertAlmostEqual(results["angles_deg"][idx], 0.0, delta=TOL,
                               msg="Slack bus angle must stay at 0°")

    # ------------------------------------------------------------------
    def test_pv_bus_voltage_fixed(self):
        """Bus 'Three' (PV) must keep |V|=1.05 pu throughout the iteration."""
        results   = self.pf.solve(self.buses, self.ybus_np, tol=TOL, max_iter=50)
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
        results   = self.pf.solve(self.buses, self.ybus_np, tol=TOL, max_iter=50)
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
    def test_pv_bus_p_spec_satisfied(self):
        """At convergence, real power injection at PV bus 'Three' must equal 5.2 pu."""
        results   = self.pf.solve(self.buses, self.ybus_np, tol=TOL, max_iter=50)
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
