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
Represents a transformer modeled as a series impedance in a conductance matrix.

**Attributes:**
- `name` (non-empty str): Transformer identifier (must be a non-empty string).
- `bus1_name` (non-empty str): Connected bus name on side 1 (must be a non-empty string).
- `bus2_name` (non-empty str): Connected bus name on side 2 (must be a non-empty string).
- `r`: Series resistance (pu or ohms, consistent with system base).
- `x`: Series reactance (pu or ohms, consistent with system base).
- `g`: Shunt conductance
- `b`: Shunt susceptance
- `admittance_matrix`: 2x2 DataFrame with bus names as index and columns.

**Notes & Warnings:**
- `name`, `bus1_name`, and `bus2_name` must be non-empty strings; ValueError is raised otherwise.
- `r`, `x`, `g`, and `b` must be non-negative; ValueError is raised otherwise.
- Both `r` and `x` cannot be zero at the same time; ValueError is raised otherwise.

**Example Usage:**
```python
t = Transformer(name="T1", bus1_name="BusA", bus2_name="BusB", r=0.02, x=0.04)
print(t.admittance_matrix)
```

---

### TransmissionLine
Transmission line model.

**Attributes:**
- `name` (non-empty str): Identifier for the line (must be a non-empty string).
- `bus1_name` (non-empty str): From-bus name (must be a non-empty string).
- `bus2_name` (non-empty str): To-bus name (must be a non-empty string).
- `r`: Series resistance (ohms).
- `x`: Series reactance (ohms).
- `g`: Series conductance (siemens), computed as r / (r^2 + x^2).
- `b`: Shunt susceptance
- `admittance_matrix`: 2x2 DataFrame with bus names as index and columns.

**Notes & Warnings:**
- `name`, `bus1_name`, and `bus2_name` must be non-empty strings; ValueError is raised otherwise.
- `r`, `x`, `g`, and `b` must be non-negative; ValueError is raised otherwise.
- Both `r` and `x` cannot be zero at the same time; ValueError is raised otherwise.

**Example Usage:**
```python
line = TransmissionLine("Line 1", "Bus 1", "Bus 2", r=0.02, x=0.25, b_shunt=0.03)
print(line.admittance_matrix)
```

---

### Circuit
Circuit class for power system network modeling. Serves as a container to assemble a complete power system network by storing and managing all equipment objects (buses, transformers, transmission lines, generators, and loads).

**Attributes:**
- `name` (non-empty str): Identifier for the circuit (must be a non-empty string).
- `buses`: Dictionary storing Bus objects with bus names as keys.
- `transformers`: Dictionary storing Transformer objects with transformer names as keys.
- `transmission_lines`: Dictionary storing TransmissionLine objects with line names as keys.
- `generators`: Dictionary storing Generator objects with generator names as keys.
- `loads`: Dictionary storing Load objects with load names as keys.

**Notes & Warnings:**
- `name` must be a non-empty string; ValueError is raised otherwise.
- Adding duplicate names for buses, transformers, transmission lines, generators, or loads will raise a ValueError.
- Adding a transformer or transmission line with bus names not present in the circuit will raise a ValueError.

**Example Usage:**
```python
circuit = Circuit("My Circuit")
circuit.add_bus("Bus 1", 138.0)
circuit.add_bus("Bus 2", 138.0)
circuit.add_generator("Gen 1", "Bus 1", voltage_setpoint=1.0, mw_setpoint=100.0)
circuit.add_load("Load 1", "Bus 2", mw=50.0, mvar=20.0)
circuit.add_transmission_line("Line 1", "Bus 1", "Bus 2", r=0.02, x=0.25)
print(circuit)
```
