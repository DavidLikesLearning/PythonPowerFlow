from transformer import Transformer
import pandas as pd
import numpy as np
import pytest

def test_invalid_name_rejected():
    with pytest.raises(ValueError):
        Transformer("", "BUS1", "BUS2", r=1.0, x=1.0)

def test_negative_r_rejected():
    with pytest.raises(ValueError):
        Transformer("L1", "BUS1", "BUS2", r=-0.1, x=1.0)

def test_undefined_when_r_and_x_zero():
    with pytest.raises(ValueError):
        t = Transformer("L1", "BUS1", "BUS2", r=0.0, x=0.0)
        assert False, f"Should be undefined when r == 0 and x == 0"

def test_admittance_matrix_properties():
    # Test admittance matrix structure
    t = Transformer("L1", "BUS1", "BUS2", r=0.2, x=0.3)
    matrix = t.admittance_matrix
    assert isinstance(matrix, pd.DataFrame)
    assert matrix.shape == (2, 2)
    assert list(matrix.index) == ["BUS1", "BUS2"]
    assert list(matrix.columns) == ["BUS1", "BUS2"]

def test_admittance_matrix_vals():
    # Test admittance matrix values
    t = Transformer("L1", "BUS1", "BUS2", r=0.2, x=0.3)
    y_expected = 1/( t.r + 1j * t.x)
    matrix = t.admittance_matrix
    assert abs(matrix.values[0,0] - y_expected) < 1e-12
    assert abs(matrix.values[1,1] - y_expected) < 1e-12
    assert abs(matrix.values[0,1] + y_expected) < 1e-12
    assert abs(matrix.values[1,0] + y_expected) < 1e-12

def test_admittance_matrix_updates():
    # Test parameter updates trigger matrix rebuild
    t = Transformer("L1", "BUS1", "BUS2", r=0.2, x=0.3)
    t.r = 0.03
    t.x = 0.06
    y_expected = 1/( t.r + 1j * t.x)
    matrix = t.admittance_matrix
    assert abs(t.admittance_matrix.values[0,0] - y_expected) < 1e-12

if __name__ == "__main__":
    test_invalid_name_rejected()
    test_negative_r_rejected()
    test_undefined_when_r_and_x_zero()
    test_admittance_matrix_properties()
    test_admittance_matrix_vals()
    test_admittance_matrix_updates()

    print("Congratulations 👌\nTransformer tests passed.")