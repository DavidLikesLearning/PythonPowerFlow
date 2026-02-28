# PythonPowerFlow

Second Project for computational power systems at UPitt. Taught by Dr. Robert Kerestes.

## Class Documentation

### Bus

Represents a bus (node) in an electrical circuit. Each bus is automatically assigned a unique index upon creation.

**Attributes:**

- `name` (str, non-empty): The name identifier of the bus (must be a non-empty string)
- `bus_index` (int): Unique index automatically assigned to each bus, incremented globally
- `nominal_kv` (float): Nominal voltage of the bus in kilovolts (read-only)
- `v` (float): The voltage at the bus in kV (set by solver, initially equals `nominal_kv`)

**Methods:**

- `_set_voltage(value)`: Sets the bus voltage — intended for use by solver classes only, not end users.
- `reset_index_counter()` *(classmethod)*: Resets the global bus index counter to 1. Useful for testing to ensure deterministic indexing.

**Notes & Warnings:**

- `v` is a read-only property for users; only solver classes should call `_set_voltage()`.
- `bus_index` is assigned automatically and increments globally across all Bus instances.

**Example Usage:**

```python
Bus.reset_index_counter()         # reset index for clean state
bus1 = Bus("Bus1", 120.0)         # index = 1
bus2 = Bus("Bus2", 240.0)         # index = 2
print(bus1)                        # Bus(name='Bus1', index=1, v=120.0V)
bus1._set_voltage(115.0)          # only called by a solver
print(bus1.v)                      # 115.0
```

---

### Load

Load model representing a power consumption element connected to a single bus.

**Attributes:**

- `name` (non-empty str): Identifier for the load (must be a non-empty string).
- `bus1_name` (non-empty str): Bus name where the load is connected (must be a non-empty string).
- `mw` (float): Real power consumption (megawatts).
- `mvar` (float): Reactive power consumption (megavolt-amperes reactive).
- `mva` (float, read-only): Apparent power (MVA), computed as `sqrt(mw² + mvar²)`.

**Notes & Warnings:**

- `name` and `bus1_name` must be non-empty strings; `ValueError` is raised otherwise.
- `mw` and `mvar` can be any float (positive, negative, or zero).
- `mva` is a computed read-only property; it updates automatically when `mw` or `mvar` change.

**Example Usage:**

```python
load = Load("LOAD1", "BUS1", mw=3.0, mvar=4.0)
print(load.mva)      # 5.0
load.mw = 6.0
print(load.mva)      # sqrt(36 + 16) ≈ 7.211
print(load)
```

---

### Generator

Generator model representing a power source connected to a single bus.

**Attributes:**

- `name` (non-empty str): Name of the generator (must be a non-empty string).
- `bus_name` (non-empty str): Name of the connected bus (must be a non-empty string).
- `mw_setpoint` (float): Active power setpoint in MW (must be finite).
- `v_setpoint` (float or None): Voltage magnitude setpoint in p.u. (must be positive if provided).

**Notes & Warnings:**

- `name` and `bus_name` must be non-empty strings; `ValueError` is raised otherwise.
- `mw_setpoint` must be a finite number; `ValueError` is raised otherwise.
- `v_setpoint` (if provided) must be a positive number; `ValueError` is raised otherwise.
- Passing a non-numeric type for `mw_setpoint` raises a `TypeError`.

**Example Usage:**

```python
g = Generator("G1", "BUS1", mw_setpoint=100.0, v_setpoint=1.05)
print(g)                   # Generator G1 at bus BUS1: P=100.0 MW, Vset=1.05 p.u.
g.mw_setpoint = 150.0
g.v_setpoint = None        # slack bus or no voltage control
```

---

### Transformer

Represents a transformer modeled as a series impedance (no magnetizing branch). The admittance matrix is a 2×2 primitive admittance matrix used for stamping into the system Y-bus.

**Attributes:**

- `name` (non-empty str): Transformer identifier (must be a non-empty string).
- `bus1_name` (non-empty str): Connected bus name on side 1 (must be a non-empty string).
- `bus2_name` (non-empty str): Connected bus name on side 2 (must be a non-empty string).
- `r` (float ≥ 0): Series resistance (pu or ohms, consistent with system base).
- `x` (float ≥ 0): Series reactance (pu or ohms, consistent with system base).
- `g` (float ≥ 0): Shunt conductance (default 0).
- `b` (float ≥ 0): Shunt susceptance (default 0).
- `admittance_matrix` (pd.DataFrame): 2×2 primitive admittance matrix with bus names as index and columns.

**Primitive Admittance Matrix Structure:**

```
         bus1_name    bus2_name
bus1_name   +Y          -Y
bus2_name   -Y          +Y
```

Where `Y = 1 / (r + jx)` is the series admittance.

**Notes & Warnings:**

- `r`, `x`, `g`, and `b` must be non-negative; `ValueError` is raised otherwise.
- Both `r` and `x` cannot be zero simultaneously; `ValueError` is raised otherwise.
- Setting any parameter (r, x, g, b) automatically rebuilds the admittance matrix.

**Example Usage:**

```python
t = Transformer(name="T1", bus1_name="BusA", bus2_name="BusB", r=0.02, x=0.04)
print(t.admittance_matrix)
t.r = 0.01               # admittance_matrix is automatically updated
```

---

### TransmissionLine

Transmission line model using the π (pi) equivalent circuit. The shunt susceptance `b` is split equally between both ends of the line.

**Attributes:**

- `name` (non-empty str): Identifier for the line (must be a non-empty string).
- `bus1_name` (non-empty str): From-bus name (must be a non-empty string).
- `bus2_name` (non-empty str): To-bus name (must be a non-empty string).
- `r` (float ≥ 0): Series resistance (ohms or pu).
- `x` (float ≥ 0): Series reactance (ohms or pu).
- `g` (float ≥ 0): Shunt conductance (default 0).
- `b` (float ≥ 0): Total line charging susceptance — split as `b/2` at each end in the π model (default 0).
- `admittance_matrix` (pd.DataFrame): 2×2 primitive admittance matrix with bus names as index and columns.

**Primitive Admittance Matrix Structure (π model):**

```
         bus1_name         bus2_name
bus1_name   Y + jb/2          -Y
bus2_name      -Y           Y + jb/2
```

Where `Y = 1 / (r + jx)` is the series admittance.

**Notes & Warnings:**

- `r`, `x`, `g`, and `b` must be non-negative; `ValueError` is raised otherwise.
- Both `r` and `x` cannot be zero simultaneously; `ValueError` is raised otherwise.
- Setting any parameter automatically rebuilds the admittance matrix.

**Example Usage:**

```python
line = TransmissionLine("Line 1", "Bus 1", "Bus 2", r=0.02, x=0.25, b=0.03)
print(line.admittance_matrix)
line.b = 0.05             # admittance_matrix is automatically updated
```

---

### Circuit

Circuit class for power system network modeling. Serves as a container to assemble a complete power system network by storing and managing all equipment objects (buses, transformers, transmission lines, generators, and loads).

**Attributes:**

- `name` (non-empty str): Identifier for the circuit (must be a non-empty string).
- `buses` (dict): Dictionary storing `Bus` objects with bus names as keys.
- `transformers` (dict): Dictionary storing `Transformer` objects with transformer names as keys.
- `transmission_lines` (dict): Dictionary storing `TransmissionLine` objects with line names as keys.
- `generators` (dict): Dictionary storing `Generator` objects with generator names as keys.
- `loads` (dict): Dictionary storing `Load` objects with load names as keys.
- `y_bus` (pd.DataFrame): The system Y-bus matrix. Raises `RuntimeError` if `build_y_bus()` has not been called yet.

**Methods:**

| Method | Description |
|--------|-------------|
| `add_bus(name, nominal_kv)` | Add a new bus to the circuit |
| `add_transformer(name, bus1_name, bus2_name, r, x, g, b)` | Add a transformer between two existing buses |
| `add_transmission_line(name, bus1_name, bus2_name, r, x, g, b)` | Add a transmission line between two existing buses |
| `add_generator(name, bus_name, voltage_setpoint, mw_setpoint)` | Add a generator connected to an existing bus |
| `add_load(name, bus1_name, mw, mvar)` | Add a load connected to an existing bus |
| `build_y_bus()` | Build (or rebuild) the system Y-bus matrix from current circuit elements |

**Notes & Warnings:**

- `name` must be a non-empty string; `ValueError` is raised otherwise.
- Adding duplicates for any component type raises a `ValueError`.
- Adding a transformer or transmission line referencing buses not yet in the circuit raises a `ValueError`.
- **`build_y_bus()` must be called after all elements are added** (or re-called after any modification) to get an up-to-date Y-bus matrix.
- Adding or modifying any branch element (transformer or transmission line) after calling `build_y_bus()` will invalidate `_y_bus` — call `build_y_bus()` again to rebuild.

**Example Usage:**

```python
circuit = Circuit("My Circuit")

# Add buses first
circuit.add_bus("Bus 1", 138.0)
circuit.add_bus("Bus 2", 138.0)
circuit.add_bus("Bus 3", 15.0)

# Add equipment (buses must exist before adding connections)
circuit.add_generator("Gen 1", "Bus 1", voltage_setpoint=1.05, mw_setpoint=100.0)
circuit.add_load("Load 1", "Bus 2", mw=50.0, mvar=20.0)
circuit.add_transmission_line("Line 1-2", "Bus 1", "Bus 2", r=0.02, x=0.25, b=0.03)
circuit.add_transformer("T1", "Bus 3", "Bus 1", r=0.005, x=0.05)

# Build Y-bus AFTER all elements are added
circuit.build_y_bus()
print(circuit.y_bus)
print(circuit)
```

---

## Y-Bus Matrix Calculation

### Overview

The **Y-bus** (bus admittance matrix) is an `n × n` complex matrix (where `n` is the number of buses) that encodes the admittance relationships between all buses in the network. It is the foundation of power flow analysis and directly used in solving the power flow equations (Newton-Raphson, Gauss-Seidel, etc.).

### Primitive Admittance Matrix

Each branch element (transmission line or transformer) has a **primitive admittance matrix** — a 2×2 DataFrame indexed by the names of the two buses it connects:

```markup
         bus_i    bus_j
bus_i    Y_ii    Y_ij
bus_j    Y_ji    Y_jj
```

- **Diagonal entries** (`Y_ii`, `Y_jj`): Sum of series admittance plus any shunt admittance (e.g., `b/2` for a π-model transmission line).
- **Off-diagonal entries** (`Y_ij`, `Y_ji`): Negative of the series admittance (`-Y_series`).

For a **transformer** (no shunt):

```markup
Y_series = 1 / (r + jx)

Y_ii = Y_jj = Y_series
Y_ij = Y_ji = -Y_series
```

For a **transmission line** (π model with shunt charging `b`):

```markup
Y_series = 1 / (r + jx)

Y_ii = Y_jj = Y_series + j(b/2)
Y_ij = Y_ji = -Y_series
```

The primitive admittance matrix captures the local electrical behavior of a single element and serves as the building block for the full system Y-bus.

### Building the System Y-Bus

`build_y_bus()` assembles the full system Y-bus by **stamping** each branch's primitive admittance matrix into the correct positions of the global `n × n` matrix:

1. **Initialization:** An `n × n` complex matrix is initialized to zero. Bus names are mapped to matrix indices in the order they were added to the circuit.

2. **Stamping branches:** For each transmission line and transformer, locate buses `i` and `j` from the bus index map, then add the 2×2 primitive matrix entries:

   ```markup
   Y[i, i] += Y_primitive[bus_i, bus_i]
   Y[i, j] += Y_primitive[bus_i, bus_j]
   Y[j, i] += Y_primitive[bus_j, bus_i]
   Y[j, j] += Y_primitive[bus_j, bus_j]
   ```

3. **Result:** The final matrix is stored as a `pd.DataFrame` with bus names as both row and column labels, accessible via `circuit.y_bus`.

### Important: When to Call `build_y_bus()`

> ⚠️ **`build_y_bus()` must be explicitly called after all circuit elements have been added.**  
> Adding any new branch element after this call will invalidate the stored Y-bus (`_y_bus` is set to `None`). Call `build_y_bus()` again before using `y_bus`.

```python
# Correct workflow:
circuit = Circuit("Example")
circuit.add_bus("One", 15.0)
circuit.add_bus("Two", 345.0)
circuit.add_transformer("T1", "One", "Two", r=0.0015, x=0.02)
circuit.add_transmission_line("L1", "Two", "Three", r=0.009, x=0.1, b=1.72)

circuit.build_y_bus()          # <-- Must call this to compute Y-bus
print(circuit.y_bus)           # Safe to access after build
```

### 5-Bus Example

```python
circuit = Circuit("5-Bus System")
circuit.add_bus("One",   15.0)
circuit.add_bus("Two",   345.0)
circuit.add_bus("Three", 15.0)
circuit.add_bus("Four",  345.0)
circuit.add_bus("Five",  345.0)

circuit.add_transmission_line("Line 4-2", "Four", "Two",  r=0.009,   x=0.1,   b=1.72)
circuit.add_transmission_line("Line 5-2", "Five", "Two",  r=0.0045,  x=0.05,  b=0.88)
circuit.add_transmission_line("Line 5-4", "Five", "Four", r=0.00225, x=0.025, b=0.44)
circuit.add_transformer("T1-5", "One",   "Five", r=0.0015,  x=0.02)
circuit.add_transformer("T3-4", "Three", "Four", r=0.00075, x=0.01)

circuit.build_y_bus()
print(circuit.y_bus)
```
