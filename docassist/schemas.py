"""Pydantic schema = the contract the LLM output must satisfy."""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Part(BaseModel):
    name: str = Field(min_length=2)
    part_number: Optional[str] = None
    quantity: int = Field(ge=1, le=1000)


class ServiceRecord(BaseModel):
    report_id: str
    service_date: date
    customer_name: str = Field(min_length=2)
    asset_id: str
    asset_type: str
    technician: str
    issue_description: str = Field(min_length=5)
    actions_taken: list[str] = Field(min_length=1)
    parts_replaced: list[Part] = Field(default_factory=list)
    labor_hours: float = Field(ge=0, le=500)
    total_cost: float = Field(ge=0)
    severity: Severity
    follow_up_required: bool
    follow_up_date: Optional[date] = None

    @field_validator("report_id", "asset_id")
    @classmethod
    def _no_whitespace(cls, v: str) -> str:
        v = v.strip()
        if not v or " " in v:
            raise ValueError("identifier must be non-empty with no spaces")
        return v

    @model_validator(mode="after")
    def _cross_field(self):
        if self.follow_up_date and self.follow_up_date < self.service_date:
            raise ValueError("follow_up_date cannot be before service_date")
        if self.follow_up_date and not self.follow_up_required:
            raise ValueError("follow_up_date given but follow_up_required is false")
        return self
