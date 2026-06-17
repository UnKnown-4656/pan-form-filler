// Global state
const state = {
    templates: {},
    currentRequest: null,
    currentView: 'dashboard',
    sourcePdfFile: null,
    formPdfFile: null,
    designer: {
        pdfData: null,
        currentPage: 0,
        totalPages: 0,
        pageWidthPts: 0,
        pageHeightPts: 0,
        templateName: '',
        templateDesc: '',
        fields: {},
        selectedFieldId: null
    }
};

function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

document.addEventListener('DOMContentLoaded', async () => {
    await checkApiHealth();
    await loadTemplates();
    setupDropzones();
    setupDashboardButtons();
    setupDesignerButtons();
});

async function checkApiHealth() {
    const badge = document.getElementById('health-badge');
    const text = document.getElementById('health-text');
    try {
        const res = await fetch('/api/v1/health');
        const data = await res.json();
        if (data.status === 'healthy') {
            badge.className = 'badge badge-online';
            text.textContent = 'System Ready';
        } else if (data.status === 'degraded') {
            badge.className = 'badge badge-warning';
            text.textContent = 'System Degraded';
        } else {
            badge.className = 'badge badge-offline';
            text.textContent = 'System Unhealthy';
        }
    } catch (e) {
        badge.className = 'badge badge-offline';
        text.textContent = 'API Unreachable';
    }
}

async function loadTemplates() {
    const select = document.getElementById('template_name');
    const desc = document.getElementById('template-desc');
    try {
        const res = await fetch('/api/v1/templates');
        const data = await res.json();
        
        // Convert templates array to an object for state.templates
        state.templates = {};
        const templatesArray = data.templates || [];
        templatesArray.forEach(tpl => {
            state.templates[tpl.name] = tpl;
        });
        
        select.innerHTML = '';
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.disabled = true;
        defaultOption.selected = true;
        defaultOption.textContent = 'Select a template...';
        select.appendChild(defaultOption);
        
        templatesArray.forEach(tpl => {
            const option = document.createElement('option');
            option.value = tpl.name;
            option.textContent = tpl.name;
            option.dataset.description = tpl.description || 'No description';
            select.appendChild(option);
        });
        
        select.addEventListener('change', (e) => {
            const selectedOption = e.target.options[e.target.selectedIndex];
            if (selectedOption && selectedOption.value) {
                desc.textContent = selectedOption.dataset.description || 'No description provided';
            } else {
                desc.textContent = 'Choose form schema configuration.';
            }
        });
    } catch (e) {
        console.error('Failed to load templates:', e);
        select.innerHTML = '<option value="" disabled selected>Failed to load templates</option>';
    }
}

function setupDropzones() {
    // Source PDF dropzone
    const sourceDropzone = document.getElementById('source-dropzone');
    const sourceInput = document.getElementById('source_pdf');
    const sourceFileInfo = document.getElementById('source-file-info');

    sourceDropzone.querySelector('.browse-btn').addEventListener('click', (e) => {
        e.preventDefault();
        sourceInput.click();
    });

    sourceInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            const file = e.target.files[0];
            state.sourcePdfFile = file;
            sourceFileInfo.textContent = `${file.name} (${formatBytes(file.size)})`;
            sourceFileInfo.classList.add('selected');
        }
    });

    sourceDropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        sourceDropzone.classList.add('dragover');
    });

    sourceDropzone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        sourceDropzone.classList.remove('dragover');
    });

    sourceDropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        sourceDropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            state.sourcePdfFile = file;
            sourceInput.files = e.dataTransfer.files;
            sourceFileInfo.textContent = `${file.name} (${formatBytes(file.size)})`;
            sourceFileInfo.classList.add('selected');
        }
    });

    // Form PDF dropzone
    const formDropzone = document.getElementById('form-dropzone');
    const formInput = document.getElementById('form_pdf');
    const formFileInfo = document.getElementById('form-file-info');

    formDropzone.querySelector('.browse-btn').addEventListener('click', (e) => {
        e.preventDefault();
        formInput.click();
    });

    formInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            const file = e.target.files[0];
            state.formPdfFile = file;
            formFileInfo.textContent = `${file.name} (${formatBytes(file.size)})`;
            formFileInfo.classList.add('selected');
        }
    });

    formDropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        formDropzone.classList.add('dragover');
    });

    formDropzone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        formDropzone.classList.remove('dragover');
    });

    formDropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        formDropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            state.formPdfFile = file;
            formInput.files = e.dataTransfer.files;
            formFileInfo.textContent = `${file.name} (${formatBytes(file.size)})`;
            formFileInfo.classList.add('selected');
        }
    });

    // Designer dropzone
    const designerDropzone = document.getElementById('designer-form-dropzone');
    const designerInput = document.getElementById('designer-form-pdf');
    const designerFileInfo = document.getElementById('designer-file-info');

    designerDropzone.querySelector('.browse-btn').addEventListener('click', (e) => {
        e.preventDefault();
        designerInput.click();
    });

    designerInput.addEventListener('change', async (e) => {
        if (e.target.files.length > 0) {
            const file = e.target.files[0];
            state.designer.pdfData = file;
            designerFileInfo.textContent = `${file.name} (${formatBytes(file.size)})`;
            designerFileInfo.classList.add('selected');
            await loadPdfPage(file, 0);
        }
    });

    designerDropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        designerDropzone.classList.add('dragover');
    });

    designerDropzone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        designerDropzone.classList.remove('dragover');
    });

    designerDropzone.addEventListener('drop', async (e) => {
        e.preventDefault();
        designerDropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            state.designer.pdfData = file;
            designerInput.files = e.dataTransfer.files;
            designerFileInfo.textContent = `${file.name} (${formatBytes(file.size)})`;
            designerFileInfo.classList.add('selected');
            await loadPdfPage(file, 0);
        }
    });
}

function setupDashboardButtons() {
    document.getElementById('design-template-btn').addEventListener('click', () => {
        document.getElementById('dashboard-view').classList.add('hidden');
        document.getElementById('template-designer-view').classList.remove('hidden');
        state.currentView = 'designer';
    });

    document.getElementById('extract-btn').addEventListener('click', async () => {
        if (!state.sourcePdfFile) {
            alert('Please upload a source PDF first');
            return;
        }
        await handleExtract();
    });

    document.getElementById('processing-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!state.sourcePdfFile) {
            alert('Please upload a source PDF');
            return;
        }
        const templateName = document.getElementById('template_name').value;
        if (!templateName) {
            alert('Please select a template');
            return;
        }
        await handleProcess();
    });
}

async function handleExtract() {
    showLoadingState('Extracting Features...', 'Locating and isolating the passport photo and handwritten signature.');
    try {
        const formData = new FormData();
        formData.append('source_pdf', state.sourcePdfFile); // Changed from 'file' to 'source_pdf'
        const res = await fetch('/api/v1/extract', { method: 'POST', body: formData });
        if (!res.ok) {
            let errorText = 'Extraction failed';
            try {
                const errorJson = await res.json();
                if (errorJson.detail) errorText = errorJson.detail;
            } catch (e) { /* ignore */ }
            throw new Error(errorText);
        }
        const data = await res.json();
        state.currentRequest = data.request_id;
        showResults(data);
    } catch (e) {
        console.error(e);
        alert('Extraction failed: ' + e.message);
    } finally {
        hideLoadingState();
    }
}

async function handleProcess() {
    showLoadingState('Filling Application Form...', 'Stamping extracted features onto the application form using the selected template.');
    try {
        const selectElement = document.getElementById('template_name');
        console.log('Select element:', selectElement);
        console.log('Select value:', selectElement.value);
        console.log('Select options:', Array.from(selectElement.options).map(o => ({ value: o.value, text: o.textContent, index: o.index, selected: o.selected })));
        
        const templateName = selectElement.value;
        if (!templateName) {
            alert('Please select a template');
            hideLoadingState();
            return;
        }

        // First, call extract to get request_id and extracted images for the results view
        let extractData;
        try {
            const extractFormData = new FormData();
            extractFormData.append('source_pdf', state.sourcePdfFile);
            const extractRes = await fetch('/api/v1/extract', { method: 'POST', body: extractFormData });
            if (!extractRes.ok) throw new Error('Extraction failed');
            extractData = await extractRes.json();
            state.currentRequest = extractData.request_id;
            showResults(extractData); // Show extracted photo and signature
        } catch (extractError) {
            // If extract fails, still proceed to process? Or show error?
            console.error('Extract failed:', extractError);
        }

        // Now call process to get the filled PDF
        const formData = new FormData();
        formData.append('source_pdf', state.sourcePdfFile);
        formData.append('template_name', templateName);
        if (state.formPdfFile) {
            formData.append('form_pdf', state.formPdfFile);
        }
        const res = await fetch('/api/v1/process', { method: 'POST', body: formData });
        if (!res.ok) {
            let errorText = 'Processing failed';
            try {
                const errorJson = await res.json();
                if (errorJson.detail) errorText = errorJson.detail;
            } catch (e) { /* ignore */ }
            throw new Error(errorText);
        }

        // Handle the PDF response
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        
        // Show the PDF in the viewer and set download link
        document.getElementById('pdf-view-btn').href = url;
        document.getElementById('pdf-download-btn').href = url;
        document.getElementById('pdf-download-btn').download = 'filled-form.pdf';
        document.getElementById('pdf-iframe').src = url;
        document.getElementById('pdf-output-card').classList.remove('hidden');

    } catch (e) {
        console.error(e);
        alert('Processing failed: ' + e.message);
    } finally {
        hideLoadingState();
    }
}

function showLoadingState(title, desc) {
    document.getElementById('loading-title').textContent = title;
    document.getElementById('loading-desc').textContent = desc;
    document.getElementById('welcome-view').classList.add('hidden');
    document.getElementById('results-view').classList.add('hidden');
    document.getElementById('loading-view').classList.remove('hidden');
}

function hideLoadingState() {
    document.getElementById('loading-view').classList.add('hidden');
}

function showResults(data) {
    document.getElementById('welcome-view').classList.add('hidden');
    document.getElementById('results-view').classList.remove('hidden');

    // Photo
    if (data.photo && data.photo.path) {
        document.getElementById('photo-placeholder').classList.add('hidden');
        document.getElementById('photo-img').src = '/extracted/' + data.request_id + '/photo.png';
        document.getElementById('photo-img').classList.remove('hidden');
        document.getElementById('photo-conf').textContent = Math.round((data.photo.confidence || 0) * 100) + '%';
        document.getElementById('photo-page').textContent = data.photo.page || 'N/A';
        const bbox = data.photo.bbox || [0, 0, 0, 0];
        document.getElementById('photo-bbox').textContent = '(' + bbox[0] + ', ' + bbox[1] + ') - (' + bbox[2] + ', ' + bbox[3] + ')';
        document.getElementById('photo-dl').href = '/extracted/' + data.request_id + '/photo.png';
        document.getElementById('photo-dl').classList.remove('disabled');
    } else {
        document.getElementById('photo-img').classList.add('hidden');
        document.getElementById('photo-placeholder').classList.remove('hidden');
    }

    // Signature
    if (data.signature && data.signature.path) {
        document.getElementById('sig-placeholder').classList.add('hidden');
        document.getElementById('sig-img').src = '/extracted/' + data.request_id + '/signature.png';
        document.getElementById('sig-img').classList.remove('hidden');
        document.getElementById('sig-conf').textContent = Math.round((data.signature.confidence || 0) * 100) + '%';
        document.getElementById('sig-page').textContent = data.signature.page || 'N/A';
        const bbox = data.signature.bbox || [0, 0, 0, 0];
        document.getElementById('sig-bbox').textContent = '(' + bbox[0] + ', ' + bbox[1] + ') - (' + bbox[2] + ', ' + bbox[3] + ')';
        document.getElementById('sig-dl').href = '/extracted/' + data.request_id + '/signature.png';
        document.getElementById('sig-dl').classList.remove('disabled');
    } else {
        document.getElementById('sig-img').classList.add('hidden');
        document.getElementById('sig-placeholder').classList.remove('hidden');
    }
}

function setupDesignerButtons() {
    document.getElementById('back-to-dashboard-btn').addEventListener('click', () => {
        document.getElementById('template-designer-view').classList.add('hidden');
        document.getElementById('dashboard-view').classList.remove('hidden');
        state.currentView = 'dashboard';
        loadTemplates();
    });

    document.getElementById('add-photo-btn').addEventListener('click', () => addNewField('photo'));
    document.getElementById('add-signature-btn').addEventListener('click', () => addNewField('signature'));
    document.getElementById('delete-field-btn').addEventListener('click', deleteSelectedField);
    document.getElementById('prev-page-btn').addEventListener('click', () => navigatePage(-1));
    document.getElementById('next-page-btn').addEventListener('click', () => navigatePage(1));
    document.getElementById('load-template-btn').addEventListener('click', loadTemplate);
    document.getElementById('save-template-btn').addEventListener('click', saveTemplate);

    setupFieldPropertyInputs();
}

async function loadPdfPage(file, pageNum) {
    try {
        const formData = new FormData();
        formData.append('pdf', file);
        formData.append('page', pageNum);

        const res = await fetch('/api/v1/pdf/render-page', { method: 'POST', body: formData });
        if (!res.ok) throw new Error('Failed to render page');

        state.designer.pageWidthPts = parseFloat(res.headers.get('X-Page-Width-Points'));
        state.designer.pageHeightPts = parseFloat(res.headers.get('X-Page-Height-Points'));
        state.designer.totalPages = parseInt(res.headers.get('X-Page-Count'));
        state.designer.currentPage = pageNum;

        const blob = await res.blob();
        const imgUrl = URL.createObjectURL(blob);

        const img = document.getElementById('pdf-page-image');
        img.src = imgUrl;
        img.style.display = 'block';

        document.getElementById('page-indicator').textContent = 'Page ' + (pageNum + 1) + ' of ' + state.designer.totalPages;
        document.getElementById('page-navigation').style.display = 'flex';
    } catch (e) {
        console.error(e);
        alert('Failed to load PDF: ' + e.message);
    }
}

async function navigatePage(delta) {
    const newPage = state.designer.currentPage + delta;
    if (newPage >= 0 && newPage < state.designer.totalPages) {
        await loadPdfPage(state.designer.pdfData, newPage);
        renderAllFields();
    }
}

function generateFieldId() {
    return 'field_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

function addNewField(fieldType) {
    if (!state.designer.pdfData) {
        alert('Please upload a PDF first');
        return;
    }
    const id = generateFieldId();
    const defaultWidthPts = fieldType === 'photo' ? 150 : 200;
    const defaultHeightPts = fieldType === 'photo' ? 150 : 60;
    const field = {
        id: id, type: fieldType, name: fieldType, page: state.designer.currentPage,
        x: 50, y: 50, width: defaultWidthPts, height: defaultHeightPts, required: true
    };
    state.designer.fields[id] = field;
    selectField(id);
    renderAllFields();
    updateFieldsList();
}

function renderAllFields() {
    const container = document.getElementById('canvas-container');
    const img = document.getElementById('pdf-page-image');
    container.querySelectorAll('.field-box').forEach(el => el.remove());
    if (!state.designer.pageWidthPts || !state.designer.pageHeightPts) return;

    const scaleX = img.clientWidth / state.designer.pageWidthPts;
    const scaleY = img.clientHeight / state.designer.pageHeightPts;

    Object.values(state.designer.fields)
        .filter(f => f.page === state.designer.currentPage)
        .forEach(field => {
            const fieldEl = document.createElement('div');
            fieldEl.className = 'field-box ' + (field.type === 'photo' ? 'photo-field' : 'signature-field');
            if (field.id === state.designer.selectedFieldId) fieldEl.classList.add('selected');
            fieldEl.dataset.fieldId = field.id;

            const left = field.x * scaleX;
            const top = field.y * scaleY;
            const width = field.width * scaleX;
            const height = field.height * scaleY;
            fieldEl.style.left = left + 'px';
            fieldEl.style.top = top + 'px';
            fieldEl.style.width = width + 'px';
            fieldEl.style.height = height + 'px';

            const label = document.createElement('div');
            label.className = 'field-label';
            label.textContent = field.name;
            fieldEl.appendChild(label);

            const handles = ['nw', 'ne', 'sw', 'se', 'n', 's', 'e', 'w'];
            handles.forEach(handle => {
                const handleEl = document.createElement('div');
                handleEl.className = 'resize-handle ' + handle;
                fieldEl.appendChild(handleEl);
            });

            let isDragging = false;
            let isResizing = false;
            let startX, startY, startFieldX, startFieldY, startWidth, startHeight, resizeHandle;

            fieldEl.addEventListener('mousedown', (e) => {
                if (e.target.classList.contains('resize-handle')) {
                    isResizing = true;
                    resizeHandle = e.target.classList[1];
                } else {
                    isDragging = true;
                }
                selectField(field.id);
                startX = e.clientX;
                startY = e.clientY;
                startFieldX = field.x;
                startFieldY = field.y;
                startWidth = field.width;
                startHeight = field.height;
                e.preventDefault();
            });

            document.addEventListener('mousemove', (e) => {
                if (!isDragging && !isResizing) return;
                const dx = (e.clientX - startX) / scaleX;
                const dy = (e.clientY - startY) / scaleY;

                if (isDragging) {
                    field.x = Math.max(0, startFieldX + dx);
                    field.y = Math.max(0, startFieldY + dy);
                } else if (isResizing) {
                    if (resizeHandle.includes('n')) {
                        const newY = startFieldY + dy;
                        const newHeight = startHeight - dy;
                        if (newHeight > 10) {
                            field.y = newY;
                            field.height = newHeight;
                        }
                    }
                    if (resizeHandle.includes('s')) {
                        field.height = Math.max(10, startHeight + dy);
                    }
                    if (resizeHandle.includes('w')) {
                        const newX = startFieldX + dx;
                        const newWidth = startWidth - dx;
                        if (newWidth > 10) {
                            field.x = newX;
                            field.width = newWidth;
                        }
                    }
                    if (resizeHandle.includes('e')) {
                        field.width = Math.max(10, startWidth + dx);
                    }
                }
                renderAllFields();
                updatePropertyInputs();
            });

            document.addEventListener('mouseup', () => {
                isDragging = false;
                isResizing = false;
            });

            container.appendChild(fieldEl);
        });
}

function selectField(id) {
    state.designer.selectedFieldId = id;
    renderAllFields();
    updateFieldsList();
    updatePropertyInputs();
}

function deleteSelectedField() {
    if (!state.designer.selectedFieldId) {
        alert('No field selected');
        return;
    }
    if (confirm('Delete this field?')) {
        delete state.designer.fields[state.designer.selectedFieldId];
        state.designer.selectedFieldId = null;
        renderAllFields();
        updateFieldsList();
        document.getElementById('field-properties').style.display = 'none';
    }
}

function updateFieldsList() {
    const container = document.getElementById('fields-list-container');
    const fields = Object.values(state.designer.fields);
    if (fields.length === 0) {
        container.innerHTML = '<p class="input-hint" style="margin:8px 0">No fields added yet</p>';
        return;
    }
    container.innerHTML = '';
    fields.forEach(field => {
        const el = document.createElement('div');
        el.className = 'field-list-item ' + (field.id === state.designer.selectedFieldId ? 'selected' : '');
        el.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center;flex-grow:1"><div style="display:flex;align-items:center;gap:12px"><div class="field-type-badge ' + field.type + '">' + (field.type === 'photo' ? 'P' : 'S') + '</div><div style="font-weight:500">' + field.name + '</div></div><div style="color:var(--text-muted);font-size:0.875rem">Page ' + (field.page + 1) + '</div></div>';
        el.addEventListener('click', () => selectField(field.id));
        container.appendChild(el);
    });
}

function setupFieldPropertyInputs() {
    ['name', 'page', 'x', 'y', 'width', 'height'].forEach(key => {
        const input = document.getElementById('field-' + key + '-input');
        if (input) {
            input.addEventListener('input', () => updateFieldFromProperty(key, input.value));
        }
    });
}

function updatePropertyInputs() {
    const field = state.designer.fields[state.designer.selectedFieldId];
    if (!field) {
        document.getElementById('field-properties').style.display = 'none';
        return;
    }
    document.getElementById('field-properties').style.display = 'block';
    document.getElementById('field-name-input').value = field.name;
    document.getElementById('field-page-input').value = field.page;
    document.getElementById('field-x-input').value = field.x.toFixed(1);
    document.getElementById('field-y-input').value = field.y.toFixed(1);
    document.getElementById('field-width-input').value = field.width.toFixed(1);
    document.getElementById('field-height-input').value = field.height.toFixed(1);
}

function updateFieldFromProperty(key, value) {
    const field = state.designer.fields[state.designer.selectedFieldId];
    if (!field) return;
    if (['x', 'y', 'width', 'height', 'page'].includes(key)) {
        field[key] = parseFloat(value) || 0;
    } else {
        field[key] = value;
    }
    renderAllFields();
    updateFieldsList();
}

async function loadTemplate() {
    const name = prompt('Enter template name to load:');
    if (!name) return;
    try {
        const res = await fetch('/api/v1/templates/' + encodeURIComponent(name));
        if (!res.ok) throw new Error('Template not found');
        const data = await res.json();
        const templateData = data.template; // because the new endpoint returns {"status":"success","template": {...}}
        state.designer.templateName = name;
        state.designer.templateDesc = templateData.description || '';
        state.designer.fields = {};
        Object.entries(templateData.fields || {}).forEach(([fieldName, fieldData]) => {
            const id = generateFieldId();
            state.designer.fields[id] = {
                id: id, type: fieldName.toLowerCase().includes('photo') ? 'photo' : 'signature',
                name: fieldName, page: fieldData.page, x: fieldData.x, y: fieldData.y,
                width: fieldData.width, height: fieldData.height, required: fieldData.required ?? true
            };
        });
        document.getElementById('template-name-input').value = name;
        document.getElementById('template-desc-input').value = state.designer.templateDesc;
        renderAllFields();
        updateFieldsList();
        alert('Template loaded!');
    } catch (e) {
        console.error(e);
        alert('Failed to load: ' + e.message);
    }
}

async function saveTemplate() {
    const name = document.getElementById('template-name-input').value.trim();
    if (!name) {
        alert('Please enter a template name');
        return;
    }
    if (Object.keys(state.designer.fields).length === 0) {
        alert('Add at least one field');
        return;
    }
    try {
        const templateData = {
            name: name, description: document.getElementById('template-desc-input').value,
            fields: {}
        };
        Object.values(state.designer.fields).forEach(field => {
            templateData.fields[field.name] = {
                page: field.page, x: field.x, y: field.y,
                width: field.width, height: field.height, required: field.required
            };
        });
        const res = await fetch('/api/v1/templates/' + encodeURIComponent(name), {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(templateData)
        });
        if (!res.ok) throw new Error('Failed to save');
        alert('Template saved!');
    } catch (e) {
        console.error(e);
        alert('Failed to save: ' + e.message);
    }
}
