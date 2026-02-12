class Load:
    """
    define load  class

    Attributes:
        name: name of the lad
        bus_name: bus name
        mw: active load
        mvar: reactive load
    """
    def __init__(self, name, bus_name, mw, mvar):
        self.name:str = name
        self.bus_name = bus_name
        self.mw:float = mw
        self.mvar:float = mvar
