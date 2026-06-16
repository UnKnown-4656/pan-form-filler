# Implementation Plan — Manual Image Placement and Coordinate Saving

The goal is to allow users to visually adjust the coordinates of the extracted `photo` and `signature` boxes directly on the form PDF page and save these coordinates as templates. This makes the tool highly versatile for daily usage across multiple projects.

In addition, the system will support placing the photo and/or signature multiple times on the same form (e.g., PAN forms requiring two photographs and multiple signature blocks).

## User Review Required

> [!IMPORTANT]
> - **Multiple Placements Support**:
>   - The backend template engine will iterate over the fields defined in the template (rather than keys in the extracted assets dict).
>   - Fields containing `"photo"` (e.g., `photo_left`, `photo_right`) will be populated using the extracted passport photo.
>   - Fields containing `"sig"` or `"signature"` (e.g., `signature_1`, `signature_2`) will be populated using the extracted handwritten signature.
> - **Template Storage**: New and edited templates will be saved back to [form_templates.json](file:///d:/Pan%20automation/pdf_autofill/app/templates/form_templates.json) in the backend. This ensures templates persist across server restarts and are immediately available to all projects.
> - **Visual Editor**: The PDF pages of the blank form template are rendered dynamically as PNGs on the backend using PyMuPDF (which is highly optimized and doesn't require complex client-side PDF renderers or external dependencies).
> - **Custom Coordinate Overrides**: In addition to saving templates, the user can adjust positions and immediately press "Auto-Fill Form" using those coordinates on-the-fly, even without saving a named template.

---

## Proposed Changes

### Backend Components

#### [MODIFY] [template_engine.py](file:///d:/Pan%20automation/pdf_autofill/app/services/template_engine.py)
- Add `save_template(name, template)`: Saves or updates a template model in `form_templates.json`.
- Add `delete_template(name)`: Deletes a template from `form_templates.json`.
- Update `fill_form` and `fill_form_from_bytes` to:
  - Iterate over the fields of the `FormTemplate` (instead of iterating over the `images` dictionary keys).
  - Map each template field to either `"photo"` or `"signature"` based on whether the field name contains `"photo"` or `"sig"`.
  - Accept an optional `custom_coords` dict to override template fields on-the-fly during processing.

#### [MODIFY] [processing.py](file:///d:/Pan%20automation/pdf_autofill/app/services/processing.py)
- Update the `process` method to accept optional `custom_coords` dictionary, and pass it to `TemplateEngine`.

#### [MODIFY] [router.py](file:///d:/Pan%20automation/pdf_autofill/app/api/router.py)
- **New endpoint**: `POST /api/v1/pdf/render-page`
  - Uploads a PDF file and page index.
  - Returns the rendered page as a PNG image.
  - Passes page dimensions (`width`, `height` in points) and total page count in response headers (`X-Page-Width-Points`, `X-Page-Height-Points`, `X-Page-Count`).
- **New endpoint**: `POST /api/v1/templates/{template_name}`
  - Saves or updates a template configuration.
- **New endpoint**: `DELETE /api/v1/templates/{template_name}`
  - Deletes a template configuration.
- **Update endpoint**: `POST /api/v1/process`
  - Accepts an optional form field `custom_coords` (JSON string) representing a custom layout coordinate set or overrides.

---

### Frontend Components

#### [MODIFY] [index.html](file:///d:/Pan%20automation/pdf_autofill/static/index.html)
- Add a "Design / Adjust Template" action button/gear icon next to the template selection dropdown.
- Add a new full-screen/side view for the **Template Designer** containing:
  - Blank PDF page image container where we render the pages.
  - Absolute-positioned draggable and resizable overlays for each field (`photo_left`, `photo_right`, `signature_1`, etc.).
  - Sidebar for manual coordinate inputs (X, Y, Width, Height, Page) in PDF points for precise adjustment.
  - Controls to add a new Photo box or Signature box (`[+ Photo]` / `[+ Signature]`) and to delete a selected box.
  - Page navigation controls (`Page X of Y`).
  - Input fields for saving: `Template Name` and `Description`.
  - Action buttons: `[Save Template]`, `[Use These Coordinates]`, `[Back to Dashboard]`.

#### [MODIFY] [style.css](file:///d:/Pan%20automation/pdf_autofill/static/style.css)
- Add style definitions for:
  - Draggable overlays (semi-transparent backgrounds, borders, resize handles).
  - Active/selected box border styles.
  - Relative canvas wrapper that keeps the PDF page image centered and coordinates aligned.
  - Controls to add/remove boxes and coordinate fine-tuning list.

#### [MODIFY] [app.js](file:///d:/Pan%20automation/pdf_autofill/static/app.js)
- Implement frontend controller logic for the Template Designer:
  - Drag-and-resize event listeners (using mouse events) to update coordinates in real time.
  - Button listeners for `[+ Photo Area]` and `[+ Signature Area]` to dynamically spawn box overlays.
  - Button listener for `[Delete Area]` to remove a box.
  - Conversion functions between browser CSS pixels and PDF points (`scale = pdf_points / client_px`).
  - Page selection change listener (refetches the blank PDF page from `/api/v1/pdf/render-page`).
  - API calls to save, load, and delete templates on the backend.
  - Passing `custom_coords` override to the `/api/v1/process` endpoint.

---

## Verification Plan

### Automated Tests
- Create a test file `tests/test_templates_api.py` to verify:
  - Template creation (`POST /api/v1/templates/{name}`) with multiple photo/signature fields.
  - Template deletion (`DELETE /api/v1/templates/{name}`).
  - Rendering of PDF page image (`POST /api/v1/pdf/render-page`).
  - Custom coordinate override processing (`POST /api/v1/process` with multiple custom fields).

### Manual Verification
1. Run the FastAPI backend server using `python main.py` or `uvicorn main:app`.
2. Open the web interface.
3. Click "Design / Adjust Template".
4. Upload a blank form PDF. It should render page 1.
5. Click `+ Photo` to add a second photo box.
6. Drag and resize both Photo boxes and the Signature box to different positions.
7. Fill in name `TEST_MANUAL_TEMPLATE` and description, and click "Save Template".
8. Verify the template is added to the template select list.
9. Process a document using the new template and verify that the photo is placed in both positions and the signature is printed where it was visually dragged.
