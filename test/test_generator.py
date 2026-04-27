import pytest
from generator import Generator

# --- Comprehensive Generator class tests ---

def test_generator_basic_creation():
    g = Generator("G1", "BUS1", mw_setpoint=100.0, v_setpoint=1.05, x_subtransient=0.2)
    assert g.name == "G1"
    assert g.bus_name == "BUS1"
    assert g.mw_setpoint == 100.0
    assert g.v_setpoint == 1.05
    assert g.x_subtransient == 0.2
    assert g.p is None

def test_generator_v_setpoint_optional():
    g = Generator("G2", "BUS2", mw_setpoint=50.0)
    assert g.v_setpoint is None
    g.v_setpoint = 1.0
    assert g.v_setpoint == 1.0


def test_generator_x_subtransient_defaults_to_one():
    g = Generator("G_default", "BUS1", mw_setpoint=100.0)
    assert g.x_subtransient == 1.0


def test_generator_x_subtransient_can_be_set_to_none():
    g = Generator("G_none", "BUS1", mw_setpoint=100.0)
    g.x_subtransient = None
    assert g.x_subtransient is None

def test_generator_repr_and_str():
    g = Generator("G3", "BUS3", mw_setpoint=100.0, v_setpoint=1.0, x_subtransient=0.25)
    rep = repr(g)
    assert "Generator(" in rep
    assert "name='G3'" in rep or 'name="G3"' in rep
    assert "bus_name='BUS3'" in rep or 'bus_name="BUS3"' in rep
    assert "mw_setpoint=100.0" in rep
    assert "v_setpoint=1.0" in rep
    assert "x_subtransient=0.25" in rep
    s = str(g)
    assert "Generator G3" in s
    assert "BUS3" in s
    assert "100.0 MW" in s
    assert "1.0 p.u." in s
    assert "X''=0.25 p.u." in s

def test_generator_setters():
    g = Generator("G4", "BUS4", mw_setpoint=10.0, v_setpoint=1.0)
    g.name = "G4A"
    assert g.name == "G4A"
    g.bus_name = "BUS4A"
    assert g.bus_name == "BUS4A"
    g.mw_setpoint = 20.0
    assert g.mw_setpoint == 20.0
    g.v_setpoint = 1.1
    assert g.v_setpoint == 1.1
    g.x_subtransient = 0.3
    assert g.x_subtransient == 0.3

def test_generator_invalid_name():
    with pytest.raises(ValueError):
        Generator("", "BUS1", mw_setpoint=10.0)
    g = Generator("G5", "BUS5", mw_setpoint=10.0)
    with pytest.raises(ValueError):
        g.name = ""

def test_generator_invalid_bus_name():
    with pytest.raises(ValueError):
        Generator("G6", "", mw_setpoint=10.0)
    g = Generator("G6", "BUS6", mw_setpoint=10.0)
    with pytest.raises(ValueError):
        g.bus_name = ""

def test_generator_invalid_mw_setpoint_type():
    with pytest.raises(TypeError):
        Generator("G7", "BUS7", mw_setpoint="100 MW") # type: ignore
    g = Generator("G7", "BUS7", mw_setpoint=10.0)
    with pytest.raises(TypeError):
        g.mw_setpoint = "bad" # type: ignore

def test_generator_invalid_mw_setpoint_infinite():
    with pytest.raises(ValueError):
        Generator("G8", "BUS8", mw_setpoint=float("inf"))
    g = Generator("G8", "BUS8", mw_setpoint=10.0)
    with pytest.raises(ValueError):
        g.mw_setpoint = float("inf")

def test_generator_invalid_v_setpoint_negative():
    with pytest.raises(ValueError):
        Generator("G9", "BUS9", mw_setpoint=10.0, v_setpoint=-1.0)
    g = Generator("G9", "BUS9", mw_setpoint=10.0, v_setpoint=1.0)
    with pytest.raises(ValueError):
        g.v_setpoint = 0.0
    with pytest.raises(ValueError):
        g.v_setpoint = -2.0

def test_generator_invalid_x_subtransient():
    with pytest.raises(ValueError):
        Generator("GX", "BUSX", mw_setpoint=10.0, x_subtransient=0.0)
    with pytest.raises(ValueError):
        Generator("GX", "BUSX", mw_setpoint=10.0, x_subtransient=-0.1)
    g = Generator("GX", "BUSX", mw_setpoint=10.0)
    with pytest.raises(ValueError):
        g.x_subtransient = 0.0
    with pytest.raises(TypeError):
        g.x_subtransient = "bad"  # type: ignore

def test_generator_calc_p():
    import math
    import settings
    g = Generator("G10", "BUS10", mw_setpoint=50.0)
    old_sbase = settings.grid_settings.sbase
    settings.grid_settings.sbase = 100.0
    p_val = g.calc_p()
    assert math.isclose(p_val, 0.5, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(g.p, 0.5, rel_tol=0, abs_tol=1e-12)
    with pytest.raises(ValueError):
        settings.grid_settings.sbase = 0.0
    settings.grid_settings.sbase = old_sbase


def test_generator_as_float_type_check():
    assert Generator._as_float(5, "field") == 5.0
    assert Generator._as_float(3.2, "field") == 3.2
    with pytest.raises(TypeError):
        Generator._as_float("bad", "field") # type: ignore
    with pytest.raises(TypeError):
        Generator._as_float(True, "field")

def test_generator_repr_contains_fields():
    g = Generator("G1", "BUS1", mw_setpoint=100.0, v_setpoint=1.0, x_subtransient=0.3)
    rep = repr(g)
    assert "Generator(" in rep
    assert "name='G1'" in rep
    assert "bus_name='BUS1'" in rep
    assert "mw_setpoint=100.0" in rep
    assert "v_setpoint=1.0" in rep
    assert "x_subtransient=0.3" in rep

def test_generator_str_human_readable():
    g = Generator("G1", "BUS1", mw_setpoint=100.0, v_setpoint=1.02)
    s = str(g)
    assert "Generator G1" in s
    assert "BUS1" in s
    assert "100.0 MW" in s
    assert "1.02 p.u." in s