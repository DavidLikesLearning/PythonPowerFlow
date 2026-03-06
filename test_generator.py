import math
import pytest
from generator import Generator

# --- Comprehensive Generator class tests ---

def test_generator_basic_creation():
    g = Generator("G1", "BUS1", mw_setpoint=100.0, v_setpoint=1.05)
    assert g.name == "G1"
    assert g.bus_name == "BUS1"
    assert g.mw_setpoint == 100.0
    assert g.v_setpoint == 1.05
    assert g.p is None

def test_generator_v_setpoint_optional():
    g = Generator("G2", "BUS2", mw_setpoint=50.0)
    assert g.v_setpoint is None
    g.v_setpoint = 1.0
    assert g.v_setpoint == 1.0

def test_generator_repr_and_str():
    g = Generator("G3", "BUS3", mw_setpoint=100.0, v_setpoint=1.0)
    rep = repr(g)
    assert "Generator(" in rep
    assert "name='G3'" in rep or 'name="G3"' in rep
    assert "bus_name='BUS3'" in rep or 'bus_name="BUS3"' in rep
    assert "mw_setpoint=100.0" in rep
    assert "v_setpoint=1.0" in rep
    s = str(g)
    assert "Generator G3" in s
    assert "BUS3" in s
    assert "100.0 MW" in s
    assert "1.0 p.u." in s

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
        Generator("G7", "BUS7", mw_setpoint="100 MW")
    g = Generator("G7", "BUS7", mw_setpoint=10.0)
    with pytest.raises(TypeError):
        g.mw_setpoint = "bad"

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

def test_generator_p_setter():
    g = Generator("G10", "BUS10", mw_setpoint=10.0)
    g.p = 0.5
    assert g.p == 0.5
    g.p = None
    assert g.p is None
    with pytest.raises(TypeError):
        g.p = "not a float"
    with pytest.raises(ValueError):
        g.p = float("inf")

def test_generator_as_float_type_check():
    assert Generator._as_float(5, "field") == 5.0
    assert Generator._as_float(3.2, "field") == 3.2
    with pytest.raises(TypeError):
        Generator._as_float("bad", "field")
    with pytest.raises(TypeError):
        Generator._as_float(True, "field")
