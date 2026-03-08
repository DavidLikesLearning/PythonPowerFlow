
from load import Load
import math
import pytest

# --- Comprehensive Load class tests ---

def test_load_basic_creation():
    load = Load("L1", "BUS1", mw=10.0, mvar=5.0)
    assert load.name == "L1"
    assert load.bus1_name == "BUS1"
    assert load.mw == 10.0
    assert load.mvar == 5.0
    assert math.isclose(load.mva, math.sqrt(10.0**2 + 5.0**2), rel_tol=0, abs_tol=1e-12)
    assert load.p is None
    assert load.q is None

def test_load_repr_and_str():
    load = Load("L2", "BUS2", mw=3.0, mvar=4.0)
    rep = repr(load)
    assert "Load(" in rep
    assert "name='L2'" in rep or 'name="L2"' in rep
    assert "bus1_name='BUS2'" in rep or 'bus1_name="BUS2"' in rep
    assert "mw=3.0" in rep
    assert "mvar=4.0" in rep
    s = str(load)
    assert "Load L2" in s
    assert "BUS2" in s
    assert "mw=3.0 MW" in s
    assert "mvar=4.0 MVAr" in s
    assert "mva=5.0 MVA" in s or "mva=5.000000 MVA" in s

def test_load_setters():
    load = Load("L3", "BUS3", mw=1.0, mvar=2.0)
    load.name = "L3A"
    assert load.name == "L3A"
    load.bus1_name = "BUS3A"
    assert load.bus1_name == "BUS3A"
    load.mw = 7.0
    assert load.mw == 7.0
    load.mvar = 8.0
    assert load.mvar == 8.0
    assert math.isclose(load.mva, math.sqrt(49.0 + 64.0), rel_tol=0, abs_tol=1e-12)

def test_load_invalid_name():
    with pytest.raises(ValueError):
        Load("", "BUS1", mw=1.0, mvar=1.0)
    load = Load("L4", "BUS4", mw=1.0, mvar=1.0)
    with pytest.raises(ValueError):
        load.name = ""

def test_load_invalid_bus1_name():
    with pytest.raises(ValueError):
        Load("L5", "", mw=1.0, mvar=1.0)
    load = Load("L5", "BUS5", mw=1.0, mvar=1.0)
    with pytest.raises(ValueError):
        load.bus1_name = ""

def test_load_zero_values():
    load = Load("L6", "BUS6", mw=0.0, mvar=0.0)
    assert math.isclose(load.mva, 0.0, rel_tol=0, abs_tol=1e-12)

def test_load_negative_values():
    load = Load("L7", "BUS7", mw=-5.0, mvar=-12.0)
    assert math.isclose(load.mva, math.sqrt(25.0 + 144.0), rel_tol=0, abs_tol=1e-12)

def test_load_calc_p_and_q():
    import settings
    load = Load("L10", "BUS10", mw=50.0, mvar=20.0)
    old_sbase = settings.grid_settings.sbase
    settings.grid_settings.sbase = 100.0
    p_val = load.calc_p()
    q_val = load.calc_q()
    assert math.isclose(p_val, 0.5, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(q_val, 0.2, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(load.p, 0.5, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(load.q, 0.2, rel_tol=0, abs_tol=1e-12)
    with pytest.raises(ValueError):
        settings.grid_settings.sbase = 0.0
    settings.grid_settings.sbase = old_sbase

def test_load_p_and_q_setters():
    load = Load("L8", "BUS8", mw=2.0, mvar=3.0)
    # Initially p and q are None
    assert load.p is None
    assert load.q is None
    # After calc_p and calc_q, p and q are updated
    load.calc_p()
    load.calc_q()
    assert math.isclose(load.p, 0.02, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(load.q, 0.03, rel_tol=0, abs_tol=1e-12)

def test_load_as_float_type_check():
    assert Load._as_float(5, "field") == 5.0
    assert Load._as_float(3.2, "field") == 3.2
    with pytest.raises(TypeError):
        Load._as_float("bad", "field") # type: ignore
    with pytest.raises(TypeError):
        Load._as_float(True, "field")

def test_load_mva_updates():
    load = Load("L9", "BUS9", mw=6.0, mvar=8.0)
    assert math.isclose(load.mva, 10.0, rel_tol=0, abs_tol=1e-12)
    load.mw = 9.0
    assert math.isclose(load.mva, math.sqrt(81.0 + 64.0), rel_tol=0, abs_tol=1e-12)
    load.mvar = 12.0
    assert math.isclose(load.mva, math.sqrt(81.0 + 144.0), rel_tol=0, abs_tol=1e-12)

if __name__ == "__main__":
    test_load_basic_creation()
    test_load_repr_and_str()
    test_load_setters()
    test_load_invalid_name()
    test_load_invalid_bus1_name()
    test_load_zero_values()
    test_load_negative_values()
    test_load_p_and_q_setters()
    test_load_as_float_type_check()
    test_load_mva_updates()

    print("Congratulations 👌\nLoad tests passed.")