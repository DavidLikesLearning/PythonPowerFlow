from __future__ import annotations

import numpy as np
import pandas as pd


class FaultStudy:
    """Balanced (3-phase) fault study using Z-bus relationships."""

    def _validate_fault_inputs(self, circuit, fault_bus_name: str, vf: complex) -> complex:
        if circuit is None:
            raise ValueError("circuit must not be None")

        if not hasattr(circuit, "buses") or not hasattr(circuit, "generators") or not hasattr(circuit, "loads"):
            raise TypeError("circuit must expose buses, generators, and loads dictionaries")

        if fault_bus_name not in circuit.buses:
            raise ValueError(f"fault_bus_name '{fault_bus_name}' is not in circuit")

        if not isinstance(vf, (int, float, complex)):
            raise TypeError("vf must be numeric")

        for gen in circuit.generators.values():
            if gen.x_subtransient is None:
                raise ValueError(
                    f"Generator '{gen.name}' is missing x_subtransient required for fault study"
                )

        return complex(vf)

    def _calc_ybus_fault(self, circuit, vprefault_dict: dict[str, float] | None = None) -> pd.DataFrame:
        """
        Build fault-condition Y-bus matrix from the circuit base Y-bus.

        Two modifications are stamped onto the diagonal:

        1. Generator Norton shunt admittance at each generator bus:
               Yg = 1 / (j * X''d)
           where X''d is the generator subtransient reactance in per unit.

        2. Load admittance at each load bus, treating each load as a
           constant-impedance element during the fault:
               Y_load = (P_pu - j*Q_pu) / |V_prefault|^2
           where P_pu and Q_pu are in per unit, and V_prefault is the pre-fault
           bus voltage magnitude. Defaults to 1.0 pu for loads not in vprefault_dict.
        """
        if vprefault_dict is None:
            vprefault_dict = {}

        ybus_base = circuit.y_bus
        ybus_fault = ybus_base.copy(deep=True)

        for gen in circuit.generators.values():
            bus_name = gen.bus_name
            if bus_name not in ybus_fault.index:
                raise ValueError(
                    f"Generator '{gen.name}' references unknown bus '{bus_name}'"
                )

            x_subtransient = gen.x_subtransient
            y_norton = 1.0 / (1j * x_subtransient)
            ybus_fault.loc[bus_name, bus_name] += y_norton

        for load in circuit.loads.values():
            bus_name = load.bus1_name
            if bus_name not in ybus_fault.index:
                raise ValueError(
                    f"Load '{load.name}' references unknown bus '{bus_name}'"
                )
            p_pu = float(load.calc_p())
            q_pu = float(load.calc_q())
            v_prefault = vprefault_dict.get(bus_name, 1.0)
            y_load = complex(p_pu, -q_pu) / (v_prefault ** 2)
            ybus_fault.loc[bus_name, bus_name] += y_load

        return ybus_fault

    def _calc_zbus_fault(self, circuit, vprefault_dict: dict[str, float] | None = None) -> pd.DataFrame:
        """Compute fault-condition Z-bus as inverse of fault-condition Y-bus."""
        ybus_fault = self._calc_ybus_fault(circuit, vprefault_dict)
        try:
            zbus_fault_np = np.linalg.inv(ybus_fault.values)
        except np.linalg.LinAlgError as exc:
            raise ValueError("Fault-condition Y-bus is singular and cannot be inverted") from exc

        return pd.DataFrame(
            zbus_fault_np,
            index=ybus_fault.index,
            columns=ybus_fault.columns,
        )

    def solve(self, circuit, vf: complex = 1.0 + 0.0j, fault_bus_name: str = "", vprefault_dict: dict[str, float] | None = None) -> dict:
        """
        Simulate a solid 3-phase fault at the requested bus.

        Parameters:
          circuit: Power system circuit model
          vf: Fault voltage magnitude (complex or float, in per unit)
          fault_bus_name: Name of the bus where the fault occurs
          vprefault_dict: Optional dict {bus_name: voltage_pu} for pre-fault bus
                          voltages. Defaults to 1.0 pu for any load bus not in
                          the dict. Used to scale load admittances per the
                          constant-impedance formula.

        Uses:
          Ifn = Vf / Znn
          Ek = (1 - Zkn / Znn) * Vf

        Returns complex per-unit values and does not mutate the input circuit.

        Examples:
          # Simple fault study with default 1.0 pu pre-fault voltages
          study = FaultStudy()
          result = study.solve(circuit, fault_bus_name="Bus2")
          print(f"Fault current: {result['ifn_pu']} pu")

          # Fault study with actual pre-fault voltages from power flow solution
          pf = PowerFlow()
          pf_result = pf.solve(circuit)
          vprefault = {bus_name: abs(pf_result["bus_voltages"][bus_name])
                       for bus_name in circuit.buses}
          result = study.solve(circuit, fault_bus_name="Bus2", vprefault_dict=vprefault)
        """
        vf_complex = self._validate_fault_inputs(circuit, fault_bus_name, vf)
        zbus_fault = self._calc_zbus_fault(circuit, vprefault_dict)
        zbus_np = zbus_fault.to_numpy(dtype=np.complex128)
        bus_names = list(zbus_fault.index)

        n = bus_names.index(fault_bus_name)
        znn = zbus_np[n, n]
        if np.isclose(abs(znn), 0.0):
            raise ZeroDivisionError("Znn is zero; cannot compute fault current")

        ifn = vf_complex / znn
        ifn_pu = float(np.abs(ifn))

        bus_voltage_magnitudes: dict[str, float] = {}
        for k, bus_name in enumerate(bus_names):
            zkn = zbus_np[k, n]
            ek = (1.0 - (zkn / znn)) * vf_complex
            bus_voltage_magnitudes[bus_name] = float(np.abs(ek))

        return {
            "fault_bus_name": fault_bus_name,
            "vf": vf_complex,
            "ifn": complex(ifn),
            "ifn_pu": ifn_pu,
            "znn": znn,
            "post_fault_bus_voltages": bus_voltage_magnitudes,
            "zbus_fault": zbus_fault,
            "ybus_fault": self._calc_ybus_fault(circuit, vprefault_dict),
        }
