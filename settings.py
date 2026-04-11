from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Settings:
    """
    System-wide settings model.

    Attributes:
        freq: System frequency (Hz). Default = 60 Hz.
        sbase: System base apparent power (MVA). Default = 100 MVA.
    """

    def __init__(self):
        self._freq: float = 60
        self._sbase: float = 100

    def __repr__(self) -> str:
        return f"Settings(freq={self._freq!r}, sbase={self._sbase!r})"

    def __str__(self) -> str:
        return (
            f"Settings: freq={self._freq} Hz, sbase={self._sbase} MVA"
        )

    # --- freq ---
    @property
    def freq(self) -> float:
        return self._freq

    @freq.setter
    def freq(self, value: float) -> None:
        if not isinstance(value, (int, float)) or value <= 0:
            raise ValueError("freq must be a positive number")
        self._freq = float(value)

    # --- sbase ---
    @property
    def sbase(self) -> float:
        return self._sbase

    @sbase.setter
    def sbase(self, value: float) -> None:
        if not isinstance(value, (int, float)) or value <= 0:
            raise ValueError("sbase must be a positive number")
        self._sbase = float(value)


# Singleton instance for system-wide access
grid_settings = Settings()