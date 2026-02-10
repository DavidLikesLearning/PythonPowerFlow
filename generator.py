class Generator:
    """
    define generator class

    Attributes:
        name: name of the generator
        bus_name: bus name
        mw_setpoint: setpoint
        v_setpoint: setpoint


    """
    def __init__(self, name, bus_name, mw_setpoint, v_setpoint=None):
        self.name = name
        self.bus_name = bus_name
        self.mw_setpoint = mw_setpoint
        self.v_setpoint = v_setpoint