"""
============================================================
 API REQUEST / RESPONSE SCHEMAS  (Pydantic v2)
============================================================
Validation lives at the edge of the system so that no malformed
reading ever reaches the feature builder. Bounds here are DELIBERATELY
WIDE - they reject the physically impossible (negative speed, absolute
zero), not the merely unusual.

That distinction matters in this project: an extreme torque reading is
precisely the fault we are trying to catch. A validator that rejected
outliers would silently discard the events the whole system exists to
detect. Unusual-but-possible values are passed through and flagged in
`input_warnings` instead.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class ReadingIn(BaseModel):
    """One sensor reading from the manual-entry panel or an API client."""

    machine_type: Literal["L", "M", "H"] = Field(
        "L", description="Product quality variant: L, M or H")
    air_temperature: float = Field(
        ..., gt=0, lt=1000, description="Air temperature (K)")
    process_temperature: float = Field(
        ..., gt=0, lt=1000, description="Process temperature (K)")
    rotational_speed: float = Field(
        ..., gt=0, lt=20000, description="Rotational speed (rpm)")
    torque: float = Field(
        ..., ge=0, lt=1000, description="Torque (Nm)")
    tool_wear: float = Field(
        ..., ge=0, lt=10000, description="Tool wear (min)")

    machine_id: Optional[str] = Field(
        None, max_length=64,
        description="Optional: persist this reading against a machine")
    cycle: Optional[int] = Field(None, ge=0)
    save: bool = Field(
        False, description="Persist the reading and any alarm it raises")
    explain: bool = Field(
        True, description="Include the per-prediction attribution")

    @field_validator("machine_type", mode="before")
    @classmethod
    def _upper(cls, v):
        return str(v).strip().upper() if v is not None else "L"

    model_config = {
        "json_schema_extra": {
            "example": {
                "machine_type": "M",
                "air_temperature": 298.1,
                "process_temperature": 308.6,
                "rotational_speed": 1551,
                "torque": 42.8,
                "tool_wear": 108,
                "explain": True,
            }
        }
    }


class MachineIn(BaseModel):
    machine_id: str = Field(..., min_length=1, max_length=64)
    name: Optional[str] = Field(None, max_length=120)
    machine_type: Literal["L", "M", "H"] = "L"
    location: Optional[str] = Field(None, max_length=120)
    commissioned: Optional[str] = None


class SimulationIn(BaseModel):
    """Start a replay."""
    machine_id: str = Field(..., min_length=1, max_length=64,
                            description="Name to run this machine under")
    source_machine: Optional[str] = Field(
        None, description="Trajectory to replay; defaults to machine_id")
    interval: float = Field(
        1.0, ge=0.05, le=10.0,
        description="Wall-clock seconds per reading")
    loop: bool = Field(False, description="Restart at the end of the run")
    restart: bool = Field(
        True, description="Clear this machine's history before starting")
    start_at: int = Field(
        0, ge=0,
        description="Begin at this reading index instead of commissioning")
    start_fraction: Optional[float] = Field(
        None, ge=0.0, le=1.0,
        description="Begin this far through the machine's life "
                    "(0.0 = new, 0.9 = near failure). Overrides start_at.")


class AcknowledgeIn(BaseModel):
    by: str = Field("operator", max_length=64)


class HealthOut(BaseModel):
    status: str
    model_loaded: bool
    dataset_available: bool
    database_ready: bool
    machines: int
    readings: int
