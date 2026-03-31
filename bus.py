"""
Bus class for power systems circuit simulation.

This module defines the Bus class which represents a bus (node) in an electrical circuit.
A bus has a name and a voltage value that can be set and retrieved.
"""
from typing import Optional
from enum import Enum

class BusType(Enum):
    Slack = "Slack"
    PQ = "PQ"
    PV = "PV"

class Bus:
    """
    Represents a bus (node) in an electrical circuit.
    
    Each bus is automatically assigned a unique index for identification.
    The voltage is calculated and set by external solver classes.
    
    Attributes:
        name (str): The name identifier of the bus
        index (int): Unique index automatically assigned to each bus
        v (float): The voltage at the bus in volts (set by solver, initially 0.0)
        nominal_kv (float): The nominal voltage of the bus in kilovolts (fixed for each bus)
        bus_type (BusType): The type of the bus (Slack, PQ, PV) 
        delta (float): The phase of the bus in degrees
        vpu (float): The voltage at the bus in per unit
    """
    
    _bus_index = 1  # Class variable to track next available index
    
    def __init__(self, name: str, nominal_kv: float, bus_type: BusType,
                 vpu: float = 1.0, delta: float = 0.0) -> None:
        """
        Initialize a Bus instance.
        
        Args:
            name (str): The name identifier of the bus
            nominal_kv (float): The nominal voltage of the bus in kilovolts
            bus_type (BusType): The bus type (Slack, PQ, PV)
            vpu (float): The voltage at the bus in per unit
            delta (float): The phase of the bus in degrees
        """
        self.name = name
        self.bus_index = Bus._bus_index
        Bus._bus_index += 1
        self._nominal_kv = nominal_kv  # Initial voltage, to be set by solver # remove attribute direct access
        self._bus_type = bus_type
        self._delta =delta
        self._vpu = vpu
        self._v = nominal_kv * self._vpu  # Internal variable to store voltage, set by solver
        self._validate_params()


    def __str__(self) -> str:
        """String representation of the Bus."""
        return f"Bus(name='{self.name}', index={self.bus_index}, v={self.nominal_kv}V)"

    def __repr__(self) -> str:
        """Official string representation of the Bus."""
        return f"Bus('{self.name}', index={self.bus_index})"

    def _validate_params(self) -> None:
        if not isinstance(self.name, str) or self.name == "":
            raise ValueError("name must be non-empty strings")
        if not isinstance(self._nominal_kv, float) or self._nominal_kv < 0:
            raise ValueError(f"nominal kv must be positive float")
        if self._bus_type not in [BusType.PQ, BusType.PV, BusType.Slack]:
            raise ValueError("bus type must be BusType class, one of BusType.PQ, BusType.PV, BusType.Slack")

        # No specific constraints on mw and mvar values (can be positive, negative, or zero)

    @property
    def v(self) -> float:
        """Get the voltage at the bus in kilovolts (read-only for users)."""
        return self._v

    @property
    def nominal_kv(self) -> float:
        """Get the nominal voltage of the bus in kilovolts (read-only for users)."""
        return self._nominal_kv
    # nominal_kv does not get a setter, it is fixed for a bus

    # --- vpu ---
    @property
    def vpu(self) -> float:
        return self._vpu

    @vpu.setter
    def vpu(self, value: float) -> None:
        if not isinstance(value, float) or value<0:
            raise ValueError("vpu must be positive float")
        self._vpu = value

    # --- delta ---
    @property
    def delta(self) -> float:
        return self._delta

    @delta.setter
    def delta(self, value: float) -> None:
        if not isinstance(value, float):
            raise ValueError("delta must be float")
        self._delta = value

    # --- delta ---
    @property
    def bus_type(self) -> BusType:
        return self._bus_type

    @bus_type.setter
    def bus_type(self, value: BusType) -> None:
        if not isinstance(value, BusType):
            raise ValueError("bus type must be one of Slack, PQ, PV")
        self._bus_type = value
    
    @classmethod
    def reset_index_counter(cls) -> None:
        """
        Reset the bus index counter to 1 (useful for testing).
        """
        cls._bus_index = 1

def main():
   pass
if __name__ == "__main__":
    main()