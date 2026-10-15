"""Shared building blocks for the user-facing models.

Every model is immutable (``frozen``), rejects unknown keywords
(``extra="forbid"``, so a typo such as ``wavelenght=`` is an error rather than
a silently ignored argument) and round-trips through JSON
(``model_dump_json`` / ``model_validate_json``), which is how Studio receives a
simulation spec. NaN and ±inf are rejected because JSON cannot carry them.

Units: lengths in µm, time in s, frequency in Hz (see ``etalon.constants``).
"""

from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    NonNegativeFloat,
    PositiveFloat,
)


def _array_to_list(value: Any) -> Any:
    """Let NumPy arrays and NumPy scalars stand in for tuples and floats."""
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


class EtalonModel(BaseModel):
    """Base class of every user-facing model: immutable, typo-proof, JSON-safe."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
        use_attribute_docstrings=True,
    )


Coordinate = Annotated[tuple[float, float, float], BeforeValidator(_array_to_list)]
"""Position (x, y, z) in µm."""

Size = Annotated[
    tuple[NonNegativeFloat, NonNegativeFloat, NonNegativeFloat],
    BeforeValidator(_array_to_list),
]
"""Extent (size_x, size_y, size_z) in µm; 0 along an axis means flat along it."""

Wavelengths = Annotated[
    tuple[PositiveFloat, ...],
    BeforeValidator(_array_to_list),
    Field(min_length=1),
]
"""One or more vacuum wavelengths in µm (a list, tuple or NumPy array)."""

FieldComponent = Literal["Ex", "Ey", "Ez", "Hx", "Hy", "Hz"]
"""Cartesian field component name."""
