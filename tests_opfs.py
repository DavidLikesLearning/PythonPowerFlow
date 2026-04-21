"""
Tests for opfs.py — compare SOCP (pf mode) and DC OPF against pandapower.

Test circuit: 3-bus, all 345 kV, 100 MVA base.

    Bus1 (Slack, V=1.00)
    Bus2 (PV,   V=1.05, P_gen=200 MW)
    Bus3 (PQ,   Load: 300 MW / 100 MVAr)

Lines (per-unit on 100 MVA, 345 kV base):
    L12: r=0.010, x=0.100, b=0.020
    L13: r=0.008, x=0.080, b=0.015
    L23: r=0.005, x=0.050, b=0.010

Generators:
    Gen1 (Bus1/Slack): cost=30 $/MWh, P_max=500 MW
    Gen2 (Bus2/PV):    cost=20 $/MWh, P_max=200 MW
"""
import numpy as np
import pandapower as pp
import pytest

from bus import BusType
from circuit import Circuit
from opfs import solve_socp, solve_dc_opf

# ── Shared constants ───────────────────────────────────────────────────────
VN_KV   = 345.0
SN_MVA  = 100.0
F_HZ    = 60.0
Z_BASE  = VN_KV**2 / SN_MVA          # 1190.25 Ω
OMEGA   = 2 * np.pi * F_HZ           # rad/s

GEN_LIMITS = {
    "Gen1": {"p_min": 0.0, "p_max": 500.0, "q_min": -300.0, "q_max": 300.0},
    "Gen2": {"p_min": 0.0, "p_max": 200.0, "q_min": -100.0, "q_max": 100.0},
}
GEN_COSTS = {"Gen1": 30.0, "Gen2": 20.0}   # $/MWh


# ── Test-circuit builders ──────────────────────────────────────────────────

def make_circuit() -> Circuit:
    """Build the 3-bus Circuit used by both SOCP and DC OPF tests."""
    c = Circuit("3bus_test")
    c.add_bus("Bus1", VN_KV, BusType.Slack, vpu=1.00)
    c.add_bus("Bus2", VN_KV, BusType.PV,   vpu=1.05)
    c.add_bus("Bus3", VN_KV, BusType.PQ)

    c.add_transmission_line("L12", "Bus1", "Bus2", r=0.010, x=0.100, b=0.020)
    c.add_transmission_line("L13", "Bus1", "Bus3", r=0.008, x=0.080, b=0.015)
    c.add_transmission_line("L23", "Bus2", "Bus3", r=0.005, x=0.050, b=0.010)

    c.add_load("Load3", "Bus3", mw=300.0, mvar=100.0)
    c.add_generator("Gen1", "Bus1", voltage_setpoint=1.00, mw_setpoint=100.0)
    c.add_generator("Gen2", "Bus2", voltage_setpoint=1.05, mw_setpoint=200.0)
    return c


def _b_to_c_nf(b_pu: float) -> float:
    """Convert per-unit shunt susceptance to nF/km (with 1 km line length)."""
    return b_pu * 1e9 / (Z_BASE * OMEGA)


def make_pandapower_net():
    """Build the same 3-bus system in pandapower (physical units)."""
    net = pp.create_empty_network(sn_mva=SN_MVA, f_hz=F_HZ)

    b1 = pp.create_bus(net, VN_KV, name="Bus1")
    b2 = pp.create_bus(net, VN_KV, name="Bus2")
    b3 = pp.create_bus(net, VN_KV, name="Bus3")

    eg_idx = pp.create_ext_grid(
        net, b1, vm_pu=1.00, name="Gen1",
        min_p_mw=0.0, max_p_mw=500.0,
        min_q_mvar=-300.0, max_q_mvar=300.0,
    )
    g2_idx = pp.create_gen(
        net, b2, p_mw=200.0, vm_pu=1.05, name="Gen2",
        min_p_mw=0.0, max_p_mw=200.0,
        min_q_mvar=-100.0, max_q_mvar=100.0,
    )
    pp.create_load(net, b3, p_mw=300.0, q_mvar=100.0, name="Load3")

    # Lines — convert pu impedances to physical Ω/km (length = 1 km)
    for name, fb, tb, r_pu, x_pu, b_pu in [
        ("L12", b1, b2, 0.010, 0.100, 0.020),
        ("L13", b1, b3, 0.008, 0.080, 0.015),
        ("L23", b2, b3, 0.005, 0.050, 0.010),
    ]:
        pp.create_line_from_parameters(
            net, fb, tb, length_km=1.0,
            r_ohm_per_km=r_pu * Z_BASE,
            x_ohm_per_km=x_pu * Z_BASE,
            c_nf_per_km=_b_to_c_nf(b_pu),
            max_i_ka=10.0, name=name,
        )

    return net, eg_idx, g2_idx


# ── SOCP pf vs pandapower AC PF ───────────────────────────────────────────

def test_socp_pf_converges():
    c = make_circuit()
    r = solve_socp(c, mode="pf")
    assert r["converged"], f"SOCP pf did not converge: {r['details']}"


def test_socp_pf_vs_pandapower_vmag():
    """SOCP pf voltage magnitudes match pandapower Newton-Raphson within 5e-3 pu."""
    c = make_circuit()
    r = solve_socp(c, mode="pf")

    net, _, _ = make_pandapower_net()
    pp.runpp(net, algorithm="nr", calculate_voltage_angles=True, max_iteration=50)

    pp_vm = net.res_bus["vm_pu"].values   # [Bus1, Bus2, Bus3]
    np.testing.assert_allclose(
        r["v_mag"], pp_vm, atol=5e-3,
        err_msg="v_mag: SOCP pf vs pandapower AC PF",
    )


def test_socp_pf_vs_pandapower_vang():
    """SOCP pf voltage angles match pandapower Newton-Raphson within 0.5°."""
    c = make_circuit()
    r = solve_socp(c, mode="pf")

    net, _, _ = make_pandapower_net()
    pp.runpp(net, algorithm="nr", calculate_voltage_angles=True, max_iteration=50)

    pp_va = net.res_bus["va_degree"].values
    np.testing.assert_allclose(
        r["v_ang_deg"], pp_va, atol=0.5,
        err_msg="v_ang_deg: SOCP pf vs pandapower AC PF",
    )


def test_socp_pf_vs_pandapower_line_flows():
    """SOCP pf from-end real power matches pandapower within 5e-3 pu."""
    c = make_circuit()
    r = solve_socp(c, mode="pf")

    net, _, _ = make_pandapower_net()
    pp.runpp(net, algorithm="nr", calculate_voltage_angles=True, max_iteration=50)

    pp_pfr = net.res_line["p_from_mw"].values / SN_MVA   # L12, L13, L23 in pu
    np.testing.assert_allclose(
        r["p_fr"], pp_pfr, atol=5e-3,
        err_msg="p_fr: SOCP pf vs pandapower AC PF",
    )


# ── DC OPF vs pandapower DC OPF ──────────────────────────────────────────

def test_dc_opf_converges():
    c = make_circuit()
    r = solve_dc_opf(c, mode="opf", gen_limits=GEN_LIMITS, gen_costs=GEN_COSTS)
    assert r["converged"], f"DC OPF did not converge: {r['details']}"


def test_dc_opf_vs_pandapower_dispatch():
    """DC OPF optimal dispatch matches pandapower DC OPF within 1 MW."""
    c = make_circuit()
    r = solve_dc_opf(c, mode="opf", gen_limits=GEN_LIMITS, gen_costs=GEN_COSTS)

    net, eg_idx, g2_idx = make_pandapower_net()
    pp.create_poly_cost(net, eg_idx, "ext_grid", cp1_eur_per_mw=GEN_COSTS["Gen1"])
    pp.create_poly_cost(net, g2_idx, "gen",      cp1_eur_per_mw=GEN_COSTS["Gen2"])
    pp.rundcopp(net, verbose=False)

    assert net["OPF_converged"], "pandapower DC OPF did not converge"

    # Gen2 is cheaper — should be at P_max=200 MW regardless of solver
    gen2_mw_our = r["details"]["p_gen_pu"][1] * SN_MVA
    gen2_mw_pp  = net.res_gen["p_mw"].values[0]
    np.testing.assert_allclose(gen2_mw_our, gen2_mw_pp, atol=1.0,
                               err_msg="Gen2 dispatch: DC OPF vs pandapower")

    gen1_mw_our = r["details"]["p_gen_pu"][0] * SN_MVA
    gen1_mw_pp  = net.res_ext_grid["p_mw"].values[0]
    np.testing.assert_allclose(gen1_mw_our, gen1_mw_pp, atol=1.0,
                               err_msg="Gen1 (slack) dispatch: DC OPF vs pandapower")


def test_dc_opf_vs_pandapower_angles():
    """DC OPF bus angles match pandapower DC OPF within 0.1°."""
    c = make_circuit()
    r = solve_dc_opf(c, mode="opf", gen_limits=GEN_LIMITS, gen_costs=GEN_COSTS)

    net, eg_idx, g2_idx = make_pandapower_net()
    pp.create_poly_cost(net, eg_idx, "ext_grid", cp1_eur_per_mw=GEN_COSTS["Gen1"])
    pp.create_poly_cost(net, g2_idx, "gen",      cp1_eur_per_mw=GEN_COSTS["Gen2"])
    pp.rundcopp(net, verbose=False)

    pp_va = net.res_bus["va_degree"].values
    np.testing.assert_allclose(
        r["v_ang_deg"], pp_va, atol=0.1,
        err_msg="v_ang_deg: DC OPF vs pandapower DC OPF",
    )


def test_dc_opf_vs_pandapower_line_flows():
    """DC OPF from-end real power matches pandapower DC OPF within 5e-3 pu."""
    c = make_circuit()
    r = solve_dc_opf(c, mode="opf", gen_limits=GEN_LIMITS, gen_costs=GEN_COSTS)

    net, eg_idx, g2_idx = make_pandapower_net()
    pp.create_poly_cost(net, eg_idx, "ext_grid", cp1_eur_per_mw=GEN_COSTS["Gen1"])
    pp.create_poly_cost(net, g2_idx, "gen",      cp1_eur_per_mw=GEN_COSTS["Gen2"])
    pp.rundcopp(net, verbose=False)

    pp_pfr = net.res_line["p_from_mw"].values / SN_MVA
    np.testing.assert_allclose(
        r["p_fr"], pp_pfr, atol=5e-3,
        err_msg="p_fr: DC OPF vs pandapower DC OPF",
    )


def test_dc_opf_lossless():
    """DC OPF p_to == -p_fr (lossless assumption)."""
    c = make_circuit()
    r = solve_dc_opf(c, mode="opf", gen_limits=GEN_LIMITS, gen_costs=GEN_COSTS)
    assert r["converged"]
    np.testing.assert_allclose(r["p_to"], -r["p_fr"], atol=1e-10,
                               err_msg="DC OPF must be lossless: p_to != -p_fr")


def test_dc_opf_power_balance():
    """DC OPF: total generation == total load (lossless)."""
    c = make_circuit()
    r = solve_dc_opf(c, mode="opf", gen_limits=GEN_LIMITS, gen_costs=GEN_COSTS)
    assert r["converged"]
    p_gen_total = sum(r["details"]["p_gen_pu"]) * SN_MVA
    np.testing.assert_allclose(p_gen_total, 300.0, atol=0.1,
                               err_msg="DC OPF power balance: gen != load")