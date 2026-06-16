"""
Pydantic models for form template definitions.

Defines the schema for JSON-based templates that specify where
extracted photos and signatures should be placed on form PDFs.
"""

from typing import Dict, Optional

from pydantic import BaseModel, Field, field_validator


class FieldPlacement(BaseModel):
    """
    Defines the position and size of a field on a form page.

    Coordinates are in PDF points (1 point = 1/72 inch).
    Origin (0, 0) is at the top-left corner of the page.
    """
    page: int = Field(
        ...,
        ge=0,
        description="Zero-based page index where this field appears.",
    )
    x: float = Field(
        ...,
        ge=0,
        description="X coordinate (left edge) in PDF points.",
    )
    y: float = Field(
        ...,
        ge=0,
        description="Y coordinate (top edge) in PDF points.",
    )
    width: float = Field(
        ...,
        gt=0,
        description="Field width in PDF points.",
    )
    height: float = Field(
        ...,
        gt=0,
        description="Field height in PDF points.",
    )
    required: bool = Field(
        default=True,
        description="Whether this field must be filled for form completion.",
    )

    @property
    def right(self) -> float:
        """Right edge X coordinate."""
        return self.x + self.width

    @property
    def bottom(self) -> float:
        """Bottom edge Y coordinate."""
        return self.y + self.height


class FormTemplate(BaseModel):
    """
    A complete form template defining all field placements.

    Supports arbitrary fields beyond just photo and signature,
    allowing for future expansion (e.g., text fields with OCR).
    """
    description: str = Field(
        default="",
        description="Human-readable description of this form template.",
    )
    page_size: str = Field(
        default="A4",
        description="Expected page size (A4, Letter, etc.). For validation only.",
    )
    fields: Dict[str, FieldPlacement] = Field(
        ...,
        description="Map of field names to their placement definitions.",
    )

    @field_validator("fields")
    @classmethod
    def validate_fields_not_empty(
        cls, v: Dict[str, FieldPlacement]
    ) -> Dict[str, FieldPlacement]:
        if not v:
            raise ValueError("Template must define at least one field.")
        return v

    def get_field(self, name: str) -> Optional[FieldPlacement]:
        """Get a field placement by name, or None if not found."""
        return self.fields.get(name)

    def has_field(self, name: str) -> bool:
        """Check if a field exists in this template."""
        return name in self.fields

    @property
    def required_fields(self) -> Dict[str, FieldPlacement]:
        """Return only the required fields."""
        return {k: v for k, v in self.fields.items() if v.required}

    @property
    def max_page_index(self) -> int:
        """Return the highest page index referenced by any field."""
        return max(f.page for f in self.fields.values())


class TemplateCollection(BaseModel):
    """
    A collection of named form templates.

    This is the root model for the form_templates.json file.
    """
    templates: Dict[str, FormTemplate] = Field(
        default_factory=dict,
        description="Map of template names to their definitions.",
    )

    def get_template(self, name: str) -> Optional[FormTemplate]:
        """Get a template by name."""
        return self.templates.get(name)

    def list_names(self) -> list[str]:
        """Return all available template names."""
        return list(self.templates.keys())
