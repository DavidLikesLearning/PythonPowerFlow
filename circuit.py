# circuit.py
from __future__ import annotations
from typing import Dict
import warnings

from bus import BusType
from bus import Bus
from transformer import Transformer
from transmissionline import TransmissionLine
from generator import Generator
from load import Load
from settings import grid_settings

import numpy as np
import pandas as pd



class Circuit:
    """
    Circuit class for power system network modeling.

    This class serves as a container to assemble a complete power system network
    by storing and managing all equipment objects (buses, transformers,
    transmission lines, generators, and loads).

    Attributes:
        name: Identifier for the circuit.
        buses: Dictionary storing Bus objects with bus names as keys.
        transformers: Dictionary storing Transformer objects with transformer names as keys.
        transmission_lines: Dictionary storing TransmissionLine objects with line names as keys.
        generators: Dictionary storing Generator objects with generator names as keys.
        loads: Dictionary storing Load objects with load names as keys.
    """

    def __init__(self, name: str):
        """
        Initialize a Circuit instance.

        Args:
            name: The circuit name (must be a non-empty string).

        Raises:
            ValueError: If name is not a non-empty string.
        """
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string")

        if name != name.strip():
            warnings.warn("Circuit name is stripped in processing. Avoid blank spaces in beginning and end of `name`.")

        self._name = name.strip()
        self._buses : Dict[str, Bus] = {}
        self._transformers : Dict[str, Transformer] = {}
        self._transmission_lines : Dict[str, TransmissionLine] = {}
        self._generators : Dict[str, Generator] = {}
        self._loads: Dict[str, Load] = {}
        self._bus_index: Dict[str, int] = {}
        self._y_bus: pd.DataFrame | None = None



    def __repr__(self) -> str:
        """Return unambiguous representation of Circuit."""
        return f"Circuit(name={self._name!r})"

    def __str__(self) -> str:
        """Return human-readable summary of Circuit."""
        return (
            f"Circuit '{self._name}': "
            f"{len(self._buses)} buses, "
            f"{len(self._transformers)} transformers, "
            f"{len(self._transmission_lines)} transmission lines, "
            f"{len(self._generators)} generators, "
            f"{len(self._loads)} loads"
        )

    # --- name property ---
    @property
    def name(self) -> str:
        """Get circuit name."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Set circuit name."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError("name must be a non-empty string")
        self._name = value.strip()

    # --- Equipment dictionary properties (read-only) ---
    @property
    def buses(self) -> dict:
        """Get buses dictionary."""
        return self._buses

    @property
    def transformers(self) -> dict:
        """Get transformers dictionary."""
        return self._transformers

    @property
    def transmission_lines(self) -> dict:
        """Get transmission lines dictionary."""
        return self._transmission_lines

    @property
    def generators(self) -> dict:
        """Get generators dictionary."""
        return self._generators

    @property
    def loads(self) -> dict:
        """Get loads dictionary."""
        return self._loads

    @property
    def y_bus(self) -> pd.DataFrame:
        """Get Y-bus matrix. Raises RuntimeError if build_y_bus() has not been called."""
        if self._y_bus is None:
            raise RuntimeError("Y-bus has not been built yet. Call build_y_bus() first.")
        return self._y_bus

    # --- Add methods ---
    def calc_ybus(self) -> pd.DataFrame:
        """
        Calculate the Y-bus matrix and bus_index mapping from the current buses
        and network elements.

        - Diagonal (i,i): sum of all admittances connected to bus i
          (including shunts from line π-models).
        - Off-diagonal (i,j): admittance between buses i and j if a connection
          exists, else 0. With TransmissionLine, this is the usual negative
          series admittance.
        """
        # No buses: empty Y-bus
        if not self.buses:
            self._bus_index = {}
            self._y_bus = pd.DataFrame(dtype=complex)
            return self._y_bus

        # Define a deterministic bus order (current dict order)
        bus_names = list(self.buses.keys())  # relies on Python 3.7+ ordered dicts
        self._bus_index = {name: idx for idx, name in enumerate(bus_names)}

        n = len(bus_names)
        Y = np.zeros((n, n), dtype=complex)

        for line in (list(self.transmission_lines.values()) +
                list(self.transformers.values())):
            y2 = line.admittance_matrix  # 2x2 DataFrame indexed by [bus1name, bus2name] [file:1]
            b1 = line.bus1_name
            b2 = line.bus2_name

            i = self._bus_index[b1]
            j = self._bus_index[b2]

            # Stamp 2x2 block
            Y[i, i] += y2.loc[b1, b1]
            Y[i, j] += y2.loc[b1, b2]
            Y[j, i] += y2.loc[b2, b1]
            Y[j, j] += y2.loc[b2, b2]

        self._y_bus = pd.DataFrame(Y, index=bus_names, columns=bus_names)
        return self._y_bus


    def add_bus(self, name: str, nominal_kv: float, bus_type: BusType) -> None:
        """
        Add a bus to the circuit.

        Args:
            name: Bus name (must be unique within buses).
            nominal_kv: Nominal voltage in kV.

        Raises:
            ValueError: If a bus with the same name already exists.
        """
        if name in self._buses:
            raise ValueError(f"Bus '{name}' already exists in circuit")

        self._buses[name] = Bus("Bus1",120.0, bus_type=BusType.PQ)

    def add_transformer(self, name: str, bus1_name: str, bus2_name: str,
                        r: float, x: float, g:float=0, b:float=0) -> None:
        """
        Add a transformer to the circuit.

        Args:
            name: Transformer name (must be unique within transformers).
            bus1_name: Primary bus name.
            bus2_name: Secondary bus name.
            r: Series resistance.
            x: Series reactance.
            g: Shunt conductance
            b: Shunt susceptance

        Raises:
            ValueError: If a transformer with the same name already exists.
        """
        if name in self._transformers:
            raise ValueError(f"Transformer '{name}' already exists in circuit")
        if bus1_name not in self._buses or bus2_name not in self._buses:
            raise ValueError(f"{bus1_name} and {bus2_name} are not both in circuit")

        self._transformers[name] = Transformer(name, bus1_name, bus2_name, r=r, x=x, g=g, b=b)
        self._y_bus = None  # invalidate Y-bus; call build_y_bus() to rebuild

    def add_transmission_line(self, name: str, bus1_name: str, bus2_name: str,
                              r: float, x: float, g:float=0, b:float=0) -> None:
        """
        Add a transmission line to the circuit.

        Args:
            name: Line name (must be unique within transmission lines).
            bus1_name: From-bus name.
            bus2_name: To-bus name.
            r: Series resistance.
            x: Series reactance.
            g: Shunt conductance.
            b: Shunt susceptance.

        Raises:
            ValueError: If a transmission line with the same name already exists.
        """
        if name in self._transmission_lines:
            raise ValueError(f"Transmission line '{name}' already exists in circuit")
        if bus1_name not in self._buses or bus2_name not in self._buses:
            raise ValueError(f"{bus1_name} and {bus2_name} are not both in circuit")
        self._transmission_lines[name] = TransmissionLine(name, bus1_name, bus2_name, r=r, x=x, b=b, g=g)
        self._y_bus = None  # invalidate Y-bus; call build_y_bus() to rebuild

    def add_generator(self, name: str, bus_name: str,
                      voltage_setpoint: float, mw_setpoint: float) -> None:
        """
        Add a generator to the circuit.

        Args:
            name: Generator name (must be unique within generators).
            bus_name: Bus name where generator is connected.
            voltage_setpoint: Voltage setpoint in per unit.
            mw_setpoint: Active power setpoint in MW.

        Raises:
            ValueError: If a generator with the same name already exists.
        """
        if name in self._generators:
            raise ValueError(f"Generator '{name}' already exists in circuit")

        self._generators[name] = Generator(name, bus_name, mw_setpoint, voltage_setpoint)

    def add_load(self, name: str, bus1_name: str, mw: float, mvar: float) -> None:
        """
        Add a load to the circuit.

        Args:
            name: Load name (must be unique within loads).
            bus1_name: Bus name where load is connected.
            mw: Active power in MW.
            mvar: Reactive power in MVAr.

        Raises:
            ValueError: If a load with the same name already exists.
        """
        if name in self._loads:
            raise ValueError(f"Load '{name}' already exists in circuit")
        self._loads[name] = Load(name, bus1_name, mw, mvar)


if __name__ == "__main__":
    pass

