from circuit import Circuit
import pandas as pd
import numpy as np

def safe_complex(s):
    s = s.strip()
    if s == "0":
        return 0j
    if 'j' in s and not s.endswith('j'):
        s = s.replace('j', '')
        for i in range(len(s)-1, 0, -1):
            if s[i] in '+-':
                s = s[:i] + s[i:] + 'j'
                break
    return complex(s)

def debug_ybus_import():
    # Load the expected Y-bus matrix from the CSV file
    csv_path = "variable_names_5bus example.csv"
    columns = pd.read_csv(csv_path, nrows=0).columns[1:]
    converters = {col: safe_complex for col in columns}
    df_expected = pd.read_csv(csv_path, index_col=0, converters=converters)

    # Create a Circuit instance and build the 5-bus example
    circuit = Circuit("5-Bus Example 6.9")
    circuit.add_bus("One", 15.0)
    circuit.add_bus("Two", 345.0)
    circuit.add_bus("Three", 15.0)
    circuit.add_bus("Four", 345.0)
    circuit.add_bus("Five", 345.0)

    circuit.add_transmission_line("L42", "Four", "Two", r=0.009, x=0.1, b=1.72)
    circuit.add_transmission_line("L13", "Five", "Two", r=0.0045, x=0.05, b=0.88)
    circuit.add_transmission_line("L23", "Five", "Four", r=0.00225, x=0.025, b=0.44)

    circuit.add_transformer("T15", "One", "Five", r=0.0015, x=0.02)
    circuit.add_transformer("T34", "Three", "Four", r=0.00075, x=0.01)

    # Extract the Y-bus matrix from the circuit
    ybus_actual = circuit._y_bus

    # Convert both DataFrames to numpy arrays without index and header
    expected_values = df_expected.values
    actual_values = ybus_actual.values

    # Ensure data types are comparable
    expected_values = expected_values.astype(np.complex_)
    actual_values = actual_values.astype(np.complex_)

    # Calculate the difference matrix
    difference_matrix = np.abs(expected_values - actual_values)

    # Print the results
    print("Expected Y-bus matrix:")
    print(expected_values)
    print("\nActual Y-bus matrix:")
    print(actual_values)
    print("\nDifference matrix (absolute values):")
    print(difference_matrix)

if __name__ == '__main__':
    debug_ybus_import()