"""Models for provider-agnostic field configuration.

These models are used across providers to configure how fields
should be set on work items.
"""

from __future__ import annotations

from pydantic import BaseModel, model_validator


class FieldConfig(BaseModel):
    """User-specified project field preferences."""

    status: str = "Backlog"
    priority: str = "P1"
    iteration: str = "active"
    size_field: str = "Size"
    size_from_tshirt: bool = True


class FieldValue(BaseModel):
    """A single project-field value to set on an item.

    At most one of the value fields should be populated.
    """

    single_select_option_id: str | None = None
    iteration_id: str | None = None
    text: str | None = None
    number: float | None = None

    @model_validator(mode="after")
    def check_at_most_one(self) -> FieldValue:
        """Ensure at most one value field is populated."""
        values = [
            self.single_select_option_id,
            self.iteration_id,
            self.text,
            self.number,
        ]
        populated = sum(v is not None for v in values)
        if populated > 1:
            msg = "Only one value field should be populated"
            raise ValueError(msg)
        return self


class ResolvedField(BaseModel):
    """A project field whose ID and target option have been resolved."""

    field_id: str
    value: FieldValue
