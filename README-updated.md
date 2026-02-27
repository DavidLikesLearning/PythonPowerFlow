# PythonPowerFlow

Second Project for computational power systems at UPitt. Taught by Dr. Robert Kerestes.


## Class Documentation

### Bus
Represents a bus (node) in an electrical circuit.

**Attributes:**
- `name` (str, non-empty): The name identifier of the bus (must be a non-empty string)
- `index` (int): Unique index automatically assigned to each bus
- `v` (float): The voltage at the bus in volts (set by solver, initially 0.0)

**Notes & Warnings:**
- All name parameters must be non-empty strings; a ValueError is raised otherwise.

**Example Usage:**
```python
bus1 = Bus("Bus1", 120.0)
bus2 = Bus("Bus2", 240.0)
print(bus1)
```

---

### Load
Load model.

**Attributes:**
- `name` (non-empty str): Identifier for the load (must be a non-empty string).
- `bus1_name` (non-empty str): Bus name where the load is connected (must be a non-empty string).
- `mw`: Real power (megawatts).
- `mvar`: Reactive power (megavolt-amperes reactive).
- `mva`: Apparent power (megavolt-amperes), computed as sqrt(mw^2 + mvar^2).

**Notes & Warnings:**
- `name` and `bus1_name` must be non-empty strings; ValueError is raised otherwise.
- `mw` and `mvar` can be any float, but must be convertible to float.

**Example Usage:**
```python
load = Load("LOAD1", "BUS1", mw=3.0, mvar=4.0)
print(load)
```

---

### Generator
Generator model.

**Attributes:**
- `name` (non-empty str): Name of the generator (must be a non-empty string).
- `bus_name` (non-empty str): Name of the connected bus (must be a non-empty string).
- `mw_setpoint`: Active power setpoint in MW (float).
- `v_setpoint`: Voltage magnitude setpoint in p.u. (float or None).

**Notes & Warnings:**
- `name` and `bus_name` must be non-empty strings; ValueError is raised otherwise.
- `mw_setpoint` must be a finite number; ValueError is raised otherwise.
- `v_setpoint` (if provided) must be a positive number; ValueError is raised otherwise.

**Example Usage:**
```python
g = Generator("G1", "BUS1", mw_setpoint=100.0, v_setpoint=1.05)
print(g)
```

---

### Transformer
Represents a transformer modeled as a series impedance with optional shunt admittance in a power system network.

**Parameters:**
- `name` (non-empty str): Transformer identifier (must be a non-empty string).
- `bus1_name` (non-empty str): Connected bus name on side 1 (must be a non-empty string).
- `bus2_name` (non-empty str): Connected bus name on side 2 (must be a non-empty string).
- `r` (float): Series resistance (pu or ohms, consistent with system base).
- `x` (float): Series reactance (pu or ohms, consistent with system base).
- `g` (float, optional): Shunt conductance (siemens), default = 0.
- `b` (float, optional): Shunt susceptance (siemens), default = 0.

**Attributes:**
- `name`: Transformer identifier.
- `bus1_name`: Connected bus name on side 1.
- `bus2_name`: Connected bus name on side 2.
- `r`: Series resistance.
- `x`: Series reactance.
- `g`: Shunt conductance.
- `b`: Shunt susceptance.
- `admittance_matrix`: 2x2 pandas DataFrame representing the primitive Y-bus matrix for this transformer, with bus names as index and columns.

**Primitive Y-bus Matrix:**
The transformer's 2x2 primitive admittance (Y-bus) matrix is automatically computed from the series impedance:
- Series admittance: `Y_series = 1 / (r + jx)`
- Shunt admittance: `Y_shunt = g + jb`
- Matrix structure:
  - `[bus1, bus1]` = `Y_series` (diagonal element for bus 1)
  - `[bus2, bus2]` = `Y_series` (diagonal element for bus 2)
  - `[bus1, bus2]` = `-Y_series` (off-diagonal coupling)
  - `[bus2, bus1]` = `-Y_series` (off-diagonal coupling)

**Notes & Warnings:**
- `name`, `bus1_name`, and `bus2_name` must be non-empty strings; ValueError is raised otherwise.
- `r`, `x`, `g`, and `b` must be non-negative; ValueError is raised otherwise.
- Both `r` and `x` cannot be zero at the same time; ValueError is raised otherwise.
- The admittance matrix is automatically rebuilt when `r`, `x`, `g`, or `b` are modified.

**Example Usage:**
```python
t = Transformer(name="T1", bus1_name="BusA", bus2_name="BusB", r=0.02, x=0.04, g=0.001, b=0.005)
print(t.admittance_matrix)
print(t)
```

---

### TransmissionLine
Transmission line model with π-model representation including shunt susceptance.

**Parameters:**
- `name` (non-empty str): Identifier for the line (must be a non-empty string).
- `bus1_name` (non-empty str): From-bus name (must be a non-empty string).
- `bus2_name` (non-empty str): To-bus name (must be a non-empty string).
- `r` (float): Series resistance (ohms).
- `x` (float): Series reactance (ohms).
- `b_shunt` (float, optional): Total shunt susceptance (siemens), default = 0.
- `g_shunt` (float, optional): Total shunt conductance (siemens), default = 0.

**Attributes:**
- `name`: Identifier for the line.
- `bus1_name`: From-bus name.
- `bus2_name`: To-bus name.
- `r`: Series resistance (ohms).
- `x`: Series reactance (ohms).
- `g`: Shunt conductance (siemens).
- `b`: Shunt susceptance (siemens).
- `admittance_matrix`: 2x2 pandas DataFrame representing the primitive Y-bus matrix for this line, with bus names as index and columns.

**Primitive Y-bus Matrix (π-model):**
The transmission line's 2x2 primitive admittance (Y-bus) matrix incorporates the π-model with shunt elements:
- Series admittance: `Y_series = 1 / (r + jx)`
- Total shunt admittance: `Y_shunt = g_shunt + j*b_shunt`
- Matrix structure (π-model splits shunt equally at each end):
  - `[bus1, bus1]` = `Y_series + j*b_shunt/2` (diagonal includes half shunt)
  - `[bus2, bus2]` = `Y_series + j*b_shunt/2` (diagonal includes half shunt)
  - `[bus1, bus2]` = `-Y_series` (off-diagonal coupling)
  - `[bus2, bus1]` = `-Y_series` (off-diagonal coupling)

**Notes & Warnings:**
- `name`, `bus1_name`, and `bus2_name` must be non-empty strings; ValueError is raised otherwise.
- `r`, `x`, `g_shunt`, and `b_shunt` must be non-negative; ValueError is raised otherwise.
- Both `r` and `x` cannot be zero at the same time; ValueError is raised otherwise.
- The π-model divides the total shunt susceptance equally between both ends of the line.
- The admittance matrix is automatically rebuilt when `r`, `x`, `g`, or `b` are modified.

**Example Usage:**
```python
line = TransmissionLine("Line 1", "Bus 1", "Bus 2", r=0.02, x=0.25, b_shunt=0.03)
print(line.admittance_matrix)
print(line)
```

---

### Circuit
Circuit class for power system network modeling. Serves as a container to assemble a complete power system network by storing and managing all equipment objects (buses, transformers, transmission lines, generators, and loads).

**Parameters:**
- `name` (non-empty str): Identifier for the circuit (must be a non-empty string).

**Attributes:**
- `name` (non-empty str): Identifier for the circuit.
- `buses` (dict): Dictionary storing Bus objects with bus names as keys.
- `transformers` (dict): Dictionary storing Transformer objects with transformer names as keys.
- `transmission_lines` (dict): Dictionary storing TransmissionLine objects with line names as keys.
- `generators` (dict): Dictionary storing Generator objects with generator names as keys.
- `loads` (dict): Dictionary storing Load objects with load names as keys.

**Internal Attributes (automatically managed):**
- `_bus_index` (dict): Dictionary mapping bus names (str) to integer indices used in the Y-bus matrix. Built automatically by `build_y_bus()`.
- `_y_bus` (pandas DataFrame): The full system Y-bus admittance matrix. Built automatically by `build_y_bus()` and updated whenever network topology changes.

**Methods:**

#### `build_y_bus() -> pd.DataFrame`
Constructs the system-wide Y-bus admittance matrix from all network elements.

**Algorithm:**
1. Creates a deterministic bus ordering from the `buses` dictionary (relies on Python 3.7+ ordered dicts).
2. Builds `_bus_index` mapping: `{bus_name: integer_index}`.
3. Initializes an n×n complex numpy array (n = number of buses).
4. Iterates through all transmission lines and transformers, stamping their 2×2 primitive Y-bus matrices into the appropriate positions of the system Y-bus matrix.
5. Returns the Y-bus as a pandas DataFrame with bus names as index and columns.

**Y-bus Matrix Construction:**
- **Diagonal elements** `[i, i]`: Sum of all admittances connected to bus i, including:
  - Series admittances from all connected lines/transformers
  - Shunt admittances from line π-models (half at each end)
  - Shunt elements from transformers
- **Off-diagonal elements** `[i, j]`: Negative of the admittance between buses i and j (coupling term).

**Returns:** 
- `pd.DataFrame`: System Y-bus matrix (complex-valued, n×n where n = number of buses).

**Notes:**
- Called automatically during `__init__` and after adding any transformer or transmission line.
- Returns an empty DataFrame if no buses exist in the circuit.

#### `add_bus(name: str, nominal_kv: float) -> None`
Add a bus to the circuit.

**Args:**
- `name` (str): Bus name (must be unique within buses).
- `nominal_kv` (float): Nominal voltage in kV.

**Raises:**
- `ValueError`: If a bus with the same name already exists.

#### `add_transformer(name: str, bus1_name: str, bus2_name: str, r: float, x: float) -> None`
Add a transformer to the circuit.

**Args:**
- `name` (str): Transformer name (must be unique within transformers).
- `bus1_name` (str): Connected bus name on side 1 (must exist in circuit).
- `bus2_name` (str): Connected bus name on side 2 (must exist in circuit).
- `r` (float): Series resistance.
- `x` (float): Series reactance.

**Raises:**
- `ValueError`: If a transformer with the same name already exists, or if either bus name is not in the circuit.

**Side Effects:**
- Rebuilds the Y-bus matrix via `build_y_bus()`.

#### `add_transmission_line(name: str, bus1_name: str, bus2_name: str, r: float, x: float) -> None`
Add a transmission line to the circuit.

**Args:**
- `name` (str): Line name (must be unique within transmission lines).
- `bus1_name` (str): From-bus name (must exist in circuit).
- `bus2_name` (str): To-bus name (must exist in circuit).
- `r` (float): Series resistance.
- `x` (float): Series reactance.

**Raises:**
- `ValueError`: If a transmission line with the same name already exists, or if either bus name is not in the circuit.

**Side Effects:**
- Rebuilds the Y-bus matrix via `build_y_bus()`.

#### `add_generator(name: str, bus_name: str, voltage_setpoint: float, mw_setpoint: float) -> None`
Add a generator to the circuit.

**Args:**
- `name` (str): Generator name (must be unique within generators).
- `bus_name` (str): Bus name where generator is connected.
- `voltage_setpoint` (float): Voltage setpoint in per unit.
- `mw_setpoint` (float): Active power setpoint in MW.

**Raises:**
- `ValueError`: If a generator with the same name already exists.

#### `add_load(name: str, bus_name: str, mw: float, mvar: float) -> None`
Add a load to the circuit.

**Args:**
- `name` (str): Load name (must be unique within loads).
- `bus_name` (str): Bus name where load is connected.
- `mw` (float): Real power in megawatts.
- `mvar` (float): Reactive power in megavolt-amperes reactive.

**Raises:**
- `ValueError`: If a load with the same name already exists.

**Notes & Warnings:**
- `name` must be a non-empty string; ValueError is raised otherwise.
- Adding duplicate names for buses, transformers, transmission lines, generators, or loads will raise a ValueError.
- Adding a transformer or transmission line with bus names not present in the circuit will raise a ValueError.
- The Y-bus matrix is automatically rebuilt whenever a transformer or transmission line is added.
- The `_bus_index` dictionary provides a mapping from bus names to matrix indices for solver implementations.

**Example Usage:**
```python
circuit = Circuit("My Circuit")
circuit.add_bus("Bus 1", 138.0)
circuit.add_bus("Bus 2", 138.0)
circuit.add_generator("Gen 1", "Bus 1", voltage_setpoint=1.0, mw_setpoint=100.0)
circuit.add_load("Load 1", "Bus 2", mw=50.0, mvar=20.0)
circuit.add_transmission_line("Line 1", "Bus 1", "Bus 2", r=0.02, x=0.25)

# Access the system Y-bus matrix
print(circuit._y_bus)

# Access bus index mapping
print(circuit._bus_index)

print(circuit)
```

---

## Key Concepts

### Primitive Y-bus Matrix
Each transmission line and transformer has its own 2×2 primitive Y-bus matrix that represents the admittance relationships between its two connected buses. This matrix is stored in the `admittance_matrix` property and is used as a building block when constructing the full system Y-bus matrix.

### System Y-bus Matrix
The Circuit class builds a complete system-wide Y-bus matrix by stamping all primitive Y-bus matrices from transmission lines and transformers into their appropriate locations. This matrix is essential for power flow analysis and is automatically maintained as the network topology changes.

### Shunt Susceptance in Transmission Lines
Transmission lines use a π-model where the total shunt susceptance `b_shunt` is split equally between the two terminal buses (b_shunt/2 at each end). This accounts for the line's capacitance and is included in the diagonal elements of both the primitive Y-bus matrix and the system Y-bus matrix.

### Bus Indexing
The `_bus_index` dictionary provides a consistent mapping from bus names to integer indices (0, 1, 2, ..., n-1) used in the Y-bus matrix. This mapping is deterministic and based on the insertion order of buses (Python 3.7+ dictionary ordering).
