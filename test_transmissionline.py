from transmissionline import TransmissionLine
import pandas as pd
import numpy as np
import pytest

def test_invalid_name_rejected():
    with pytest.raises(ValueError):
        TransmissionLine("", "BUS1", "BUS2", r=1.0, x=1.0)

def test_negative_r_rejected():
    with pytest.raises(ValueError):
        TransmissionLine("L1", "BUS1", "BUS2", r=-0.1, x=1.0)

def test_undefined_when_r_and_x_zero():
    with pytest.raises(ValueError):
        line = TransmissionLine("L1", "BUS1", "BUS2", r=0.0, x=0.0)
        assert False, f"Should be undefined when r == 0 and x == 0"
#---------------------------------------------------------------------------#
# admittance_matrix tests
#---------------------------------------------------------------------------#

def test_y_matrix_returns_dataframe():
    line1 = TransmissionLine("Line 1", "Bus 1", "Bus 2",
                             r=0.02, x=0.25)
    y_matrix = line1.admittance_matrix
    assert isinstance(y_matrix, pd.DataFrame), "calc_y_matrix() should return a pd.DataFrame"

def test_y_matrix_shape():
    line1 = TransmissionLine("Line 1", "Bus 1", "Bus 2",
                             r=0.02, x=0.25)
    y_matrix = line1.admittance_matrix
    assert y_matrix.shape == (2, 2), "admittance_matrix must be a 2x2 matrix"

def test_y_matrix_bus_labels():
    line1 = TransmissionLine("Line 1", "Bus 1", "Bus 2",
                             r=0.02, x=0.25)
    y_matrix = line1.admittance_matrix
    assert list(y_matrix.index)   == ["Bus 1", "Bus 2"]
    assert list(y_matrix.columns) == ["Bus 1", "Bus 2"]

def test_y_matrix_elements():
    """
    Each diagonal element should equal Yseries + Yshunt/2
    (pi-model: half the shunt at each end).
    """
    line1 = TransmissionLine("Line 1", "Bus 1", "Bus 2",
                             r=0.02, x=0.25, b = .03)
    y_matrix = line1.admittance_matrix
    expected_element = 1/(line1.r+1j*line1.x) + 1j*.03 *1/2
    assert y_matrix.values[0,0] - expected_element < 1e-7, f"Expected {expected_element}, got {y_matrix.values[0,0]}"
    assert y_matrix.values[1,1] - expected_element < 1e-7, f"Expected {expected_element}, got {y_matrix.values[1,1]}"
    assert y_matrix.values[0,1] + expected_element < 1e-7, f"Expected {-expected_element}, got {y_matrix.values[0,1]}"
    assert y_matrix.values[1,0] + expected_element < 1e-7, f"Expected {-expected_element}, got {y_matrix.values[1,0]}"

def test_y_matrix_off_diagonal_elements():
    """Off-diagonal elements should equal -Yseries."""
    line1 = TransmissionLine("Line 1", "Bus 1", "Bus 2",
                             r=0.02, x=0.25, b = .03)
    y_matrix = line1.admittance_matrix
    expected_off = 1/(line1.r+1j*line1.x)
    print('\nAdmittance Matrix:\n',y_matrix)
    assert y_matrix.values[0,0] - expected_off < 1e-7, f"Expected {expected_off}, got {y_matrix.values[0,0]}"
    assert y_matrix.values[1,1] - expected_off < 1e-7, f"Expected {expected_off}, got {y_matrix.values[1,1]}"
   

if __name__ == "__main__":
    test_invalid_name_rejected()
    test_negative_r_rejected()
    test_undefined_when_r_and_x_zero()
    test_y_matrix_elements()
    test_y_matrix_off_diagonal_elements()

    print("Congratulations 👌\nTransmission tests passed.")