"""
Template engine — loads form templates and inserts images into PDFs.

Handles the final stage of the pipeline: taking extracted photo/signature
images and placing them at predefined coordinates on form PDF documents.

Uses PyMuPDF (pymupdf) for all PDF manipulation.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import pymupdf

from app.config import settings
from app.models.template import FieldPlacement, FormTemplate, TemplateCollection

logger = logging.getLogger(__name__)


class TemplateEngine:
    """
    Manages form templates and inserts images into PDF forms.

    Templates are loaded from a JSON file and cached in memory.
    Image insertion uses PyMuPDF's native insert_image() method.

    Usage:
        engine = TemplateEngine()
        engine.load_templates()
        output_path = engine.fill_form(
            template_name="PAN_FORM_V1",
            form_pdf_path=Path("blank_form.pdf"),
            images={"photo": Path("photo.png"), "signature": Path("sig.png")},
            output_path=Path("completed.pdf"),
        )
    """

    def __init__(
        self,
        templates_dir: Optional[Path] = None,
    ) -> None:
        self._templates_dir = templates_dir or settings.TEMPLATES_DIR
        self._templates: Dict[str, FormTemplate] = {}
        self._loaded = False

    def _get_json_path(self) -> Path:
        return self._templates_dir / "form_templates.json"

    def load_templates(
        self,
        json_path: Optional[Path] = None,
    ) -> None:
        """
        Load form templates from the JSON configuration file.

        Args:
            json_path: Override the default templates file path.
                       Defaults to <templates_dir>/form_templates.json.

        Raises:
            FileNotFoundError: If the JSON file doesn't exist.
            ValueError: If the JSON is invalid or fails validation.
        """
        path = json_path or self._get_json_path()

        if not path.exists():
            logger.warning("Templates file not found: %s", path)
            self._templates = {}
            self._loaded = True
            return

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))

            # The JSON file is a flat dict of template_name → template_data.
            # Wrap it into our TemplateCollection model.
            collection = TemplateCollection(templates={
                name: FormTemplate(**data) for name, data in raw.items()
            })

            self._templates = dict(collection.templates)
            self._loaded = True

            logger.info(
                "Loaded %d form template(s) from %s: %s",
                len(self._templates),
                path,
                ", ".join(self._templates.keys()),
            )

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in templates file: {e}") from e
        except Exception as e:
            raise ValueError(f"Failed to parse templates: {e}") from e

    def save_template(self, name: str, template: FormTemplate) -> None:
        """
        Save or update a template to the JSON file.

        Args:
            name: Name of the template
            template: FormTemplate object to save
        """
        path = self._get_json_path()
        self._templates[name] = template
        
        # Convert templates to dict for JSON serialization
        templates_dict = {}
        for tmpl_name, tmpl in self._templates.items():
            # Convert FieldPlacement objects to dicts
            fields_dict = {}
            for field_name, field in tmpl.fields.items():
                fields_dict[field_name] = {
                    "page": field.page,
                    "x": field.x,
                    "y": field.y,
                    "width": field.width,
                    "height": field.height,
                    "required": field.required
                }
            templates_dict[tmpl_name] = {
                "description": tmpl.description,
                "page_size": tmpl.page_size,
                "fields": fields_dict
            }
        
        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to file
        path.write_text(json.dumps(templates_dict, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Template '%s' saved", name)

    def delete_template(self, name: str) -> bool:
        """
        Delete a template from the JSON file.

        Args:
            name: Name of the template to delete

        Returns:
            True if template was deleted, False if it didn't exist
        """
        if name not in self._templates:
            return False
        
        del self._templates[name]
        
        # Convert remaining templates to dict for JSON serialization
        templates_dict = {}
        for tmpl_name, tmpl in self._templates.items():
            fields_dict = {}
            for field_name, field in tmpl.fields.items():
                fields_dict[field_name] = {
                    "page": field.page,
                    "x": field.x,
                    "y": field.y,
                    "width": field.width,
                    "height": field.height,
                    "required": field.required
                }
            templates_dict[tmpl_name] = {
                "description": tmpl.description,
                "page_size": tmpl.page_size,
                "fields": fields_dict
            }
        
        path = self._get_json_path()
        path.write_text(json.dumps(templates_dict, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Template '%s' deleted", name)
        return True

    def get_template(self, name: str) -> Optional[FormTemplate]:
        """
        Get a template by name.

        Auto-loads templates on first access if not yet loaded.
        """
        if not self._loaded:
            self.load_templates()
        return self._templates.get(name)

    def list_templates(self) -> List[str]:
        """Return all available template names."""
        if not self._loaded:
            self.load_templates()
        return list(self._templates.keys())

    def _get_image_for_field(self, field_name: str, images: Dict[str, Path]) -> Optional[Path]:
        """
        Get the appropriate image for a field based on field name.
        Fields containing 'photo' use the 'photo' image.
        Fields containing 'sig' or 'signature' use the 'signature' image.
        """
        lower_name = field_name.lower()
        if 'photo' in lower_name and 'photo' in images:
            return images['photo']
        if ('sig' in lower_name or 'signature' in lower_name) and 'signature' in images:
            return images['signature']
        # Fallback to exact match if exists
        return images.get(field_name)

    def fill_form(
        self,
        template_name: str,
        form_pdf_path: Path,
        images: Dict[str, Path],
        output_path: Path,
        custom_coords: Optional[Dict[str, FieldPlacement]] = None,
    ) -> Path:
        """
        Insert extracted images into a form PDF at template-defined positions.

        Args:
            template_name: Name of the template to use (e.g., "PAN_FORM_V1").
            form_pdf_path: Path to the blank form PDF.
            images: Map of field names to image file paths
                    (e.g., {"photo": Path("photo.png"), "signature": Path("sig.png")}).
            output_path: Where to save the completed PDF.
            custom_coords: Optional custom field coordinates to override template

        Returns:
            Path to the saved completed PDF.

        Raises:
            ValueError: If template not found or form PDF invalid.
            FileNotFoundError: If form PDF or image files don't exist.
        """
        # Validate template.
        template = self.get_template(template_name)
        if template is None:
            available = ", ".join(self.list_templates()) or "(none)"
            raise ValueError(
                f"Template '{template_name}' not found. "
                f"Available templates: {available}"
            )

        # Validate form PDF.
        if not form_pdf_path.exists():
            raise FileNotFoundError(f"Form PDF not found: {form_pdf_path}")

        # Open the form PDF and insert images.
        try:
            doc = pymupdf.open(str(form_pdf_path))
            page_count = len(doc)

            insertions_done = 0

            # Iterate over template fields instead of images dict
            for field_name, field_def in template.fields.items():
                # Use custom coords if provided for this field
                field = custom_coords.get(field_name, field_def) if custom_coords else field_def
                
                # Get appropriate image for this field
                image_path = self._get_image_for_field(field_name, images)
                
                if not image_path:
                    logger.warning(
                        "No image available for field '%s', skipping",
                        field_name,
                    )
                    continue

                if not image_path.exists():
                    logger.warning(
                        "Image file missing for field '%s': %s",
                        field_name,
                        image_path,
                    )
                    continue

                # Validate page index.
                if field.page >= page_count:
                    logger.error(
                        "Field '%s' references page %d, but PDF has only %d pages",
                        field_name,
                        field.page,
                        page_count,
                    )
                    continue

                # Get the target page.
                page = doc[field.page]

                # Define the insertion rectangle.
                # PyMuPDF Rect: (x0, y0, x1, y1) = (left, top, right, bottom)
                rect = pymupdf.Rect(
                    field.x,
                    field.y,
                    field.right,
                    field.bottom,
                )

                # Insert the image.
                page.insert_image(
                    rect,
                    filename=str(image_path),
                    keep_proportion=True,
                    overlay=True,
                )

                insertions_done += 1
                logger.info(
                    "Inserted '%s' on page %d at (%0.f, %.0f, %.0f, %.0f)",
                    field_name,
                    field.page,
                    field.x,
                    field.y,
                    field.right,
                    field.bottom,
                )

            # Save the completed PDF.
            output_path.parent.mkdir(parents=True, exist_ok=True)
            doc.save(str(output_path))
            doc.close()

            logger.info(
                "Form completed: %d fields filled, saved to %s",
                insertions_done,
                output_path,
            )
            return output_path

        except pymupdf.FileDataError as e:
            raise ValueError(f"Invalid form PDF: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Form filling failed: {e}") from e

    def fill_form_from_bytes(
        self,
        template_name: str,
        form_pdf_bytes: bytes,
        images: Dict[str, Path],
        output_path: Path,
        custom_coords: Optional[Dict[str, FieldPlacement]] = None,
    ) -> Path:
        """
        Same as fill_form but accepts the form PDF as raw bytes.

        Useful when the form PDF is uploaded via the API rather than
        stored on disk.
        """
        template = self.get_template(template_name)
        if template is None:
            raise ValueError(f"Template '{template_name}' not found.")

        try:
            doc = pymupdf.open(stream=form_pdf_bytes, filetype="pdf")
            page_count = len(doc)

            insertions_done = 0

            # Iterate over template fields instead of images dict
            for field_name, field_def in template.fields.items():
                # Use custom coords if provided for this field
                field = custom_coords.get(field_name, field_def) if custom_coords else field_def
                
                # Get appropriate image for this field
                image_path = self._get_image_for_field(field_name, images)
                
                if not image_path or not image_path.exists():
                    continue

                if field.page >= page_count:
                    continue

                page = doc[field.page]
                rect = pymupdf.Rect(
                    field.x, field.y, field.right, field.bottom
                )
                page.insert_image(rect, filename=str(image_path),
                                  keep_proportion=True, overlay=True)
                
                insertions_done += 1

            output_path.parent.mkdir(parents=True, exist_ok=True)
            doc.save(str(output_path))
            doc.close()

            logger.info(
                "Form completed: %d fields filled, saved to %s",
                insertions_done,
                output_path,
            )
            return output_path

        except Exception as e:
            raise RuntimeError(f"Form filling from bytes failed: {e}") from e
