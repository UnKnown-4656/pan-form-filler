// Global state
const state = {
    templates: {},
    currentRequest: null,
    currentView: 'dashboard',
    sourcePdfFile: null,
    formPdfFile: null,
    
    // Template Designer state
    designer: {
        pdfData: null,
        currentPage: 0,
        totalPages: 0,
        pageWidthPts: 0,
        pageHeightPts: 0,
        templateName: '',
        templateDesc: '',
        fields: {},
        selectedFieldId: null,
        isDragging: false,
        isResizing: false,
        dragStartX: 0,
        dragStartY: 0,
        resizeHandle: null
    }
};

// Helper: Format bytes to human-readable
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

// Helper: Show toast notification
function showToast(message, type = 'info') {
    // Simple toast (we'll just use alert for now, or add a toast div)
    console.log(`[${type.toUpperCase()}] ${message}`);
}

// Helper: Generate unique field ID
function generateFieldId() {
    return 'field_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// Initialize app
document.addEventListener('DOMContentLoaded', async () => {
    await checkApiHealth();
    await loadTemplates();
    initDashboardListeners();
    initDesignerListeners();
});

// Check API Health
async function checkApiHealth() {
    const badge = document.getElementById('health-badge');
    const text = document.getElementById('health-text');
    try {
        const res = await fetch('/api/v1/health');
        const data = await res.json();
        if (data.status === 'ok') {
            badge.className = 'badge badge-online';
            text.textContent = 'System Ready';
        } else {
            badge.className = 'badge badge-offline';
            text.textContent = 'System Unhealthy';
        }
    } catch (e) {
        badge.className = 'badge badge-offline';
        text.textContent = 'API Unreachable';
    }
}

// Load templates from API
async function loadTemplates() {
    const select = document.getElementById('template_name');
    const desc = document.getElementById('template-desc');
    try {
        const res = await fetch('/api/v1/templates');
        const data = await res.json();
        state.templates = data.templates || {};
        
        select.innerHTML = '';
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.disabled = true;
        defaultOption.selected = true;
        defaultOption.textContent = 'Select a template...';
        select.appendChild(defaultOption);
        
        Object.entries(state.templates).forEach(([name, tpl]) => {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = name;
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

// Initialize Dashboard Listeners
function initDashboardListeners() {
    setupDropzone('source-dropzone', 'source-file-info', (file) => {
        state.sourcePdfFile = file;
    });
    
    setupDropzone('form-dropzone', 'form-file-info', (file) => {
        state.formPdfFile = file;
    });
    
    document.getElementById('design-template-btn').addEventListener('click', openTemplateDesigner);
    
    document.getElementById('extract-btn').addEventListener('click', handleExtract);
    document.getElementById('processing-form').addEventListener('submit', handleProcess);
}

// Setup Dropzone
function setupDropzone(dropzoneId, fileInfoId, onFileSelected) {
    const dropzone = document.getElementById(dropzoneId);
    const fileInput = dropzone.querySelector('input[type="file"]');
    const fileInfo = document.getElementById(fileInfoId);

    const preventDefaults = (e) => {
        e.preventDefault();
        e.stopPropagation();
    };

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, preventDefaults, false);
    });

    dropzone.addEventListener('dragover', () => dropzone.classList.add('dragover'), false);
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'), false);
    dropzone.addEventListener('drop', () => dropzone.classList.remove('dragover'), false);

    const handleFile = (file) => {
        fileInfo.textContent = `${file.name} (${formatBytes(file.size)})`;
        fileInfo.classList.add('selected');
        if (onFileSelected) onFileSelected(file);
    };

    dropzone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            handleFile(files[0]);
        }
    }, false);

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });

    // Make browse button trigger file input
    const browseBtn = dropzone.querySelector('.browse-btn');
    if (browseBtn) {
        browseBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            fileInput.click();
        });
    }
}

// Switch to template designer view
function openTemplateDesigner() {
    state.currentView = 'designer';
    document.getElementById('dashboard-view').classList.add('hidden');
    document.getElementById('template-designer-view').classList.remove('hidden');
}

// Switch back to dashboard view
function closeTemplateDesigner() {
    state.currentView = 'dashboard';
    document.getElementById('template-designer-view').classList.add('hidden');
    document.getElementById('dashboard-view').classList.remove('hidden');
    loadTemplates(); // Refresh templates in dropdown
}

// Handle Extract Only
async function handleExtract() {
    if (!state.sourcePdfFile) {
        alert('Please upload a source PDF first');
        return;
    }
    
    showLoadingState('Extracting Features...', 'Locating and isolating the passport photo and handwritten signature.');
    
    try {
        const formData = new FormData();
        formData.append('file', state.sourcePdfFile);
        
        const res = await fetch('/api/v1/extract', {
            method: 'POST',
            body: formData
        });
        
        if (!res.ok) {
            throw new Error('Extraction failed');
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

// Handle Process (Fill Form)
async function handleProcess(e) {
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
    
    showLoadingState('Filling Application Form...', 'Stamping extracted features onto the application form using the selected template.');
    
    try {
        const formData = new FormData();
        formData.append('source_pdf', state.sourcePdfFile);
        formData.append('template_name', templateName);
        
        if (state.formPdfFile) {
            formData.append('form_pdf', state.formPdfFile);
        }
        
        const res = await fetch('/api/v1/process', {
            method: 'POST',
            body: formData
        });
        
        if (!res.ok) {
            throw new Error('Processing failed');
        }
        
        const data = await res.json();
        state.currentRequest = data.request_id;
        
        showResults(data);
        
        if (data.output_file) {
            const downloadBtn = document.getElementById('pdf-download-btn');
            downloadBtn.href = `/output/${data.output_file}`;
            downloadBtn.download = data.output_file;
            
            const viewBtn = document.getElementById('pdf-view-btn');
            viewBtn.href = `/output/${data.output_file}`;
            
            const iframe = document.getElementById('pdf-iframe');
            iframe.src = `/output/${data.output_file}`;
            
            document.getElementById('pdf-output-card').classList.remove('hidden');
        }
    } catch (e) {
        console.error(e);
        alert('Processing failed: ' + e.message);
    } finally {
        hideLoadingState();
    }
}

// Show loading state
function showLoadingState(title, desc) {
    document.getElementById('loading-title').textContent = title;
    document.getElementById('loading-desc').textContent = desc;
    document.getElementById('welcome-view').classList.add('hidden');
    document.getElementById('results-view').classList.add('hidden');
    document.getElementById('loading-view').classList.remove('hidden');
    
    let progress = 0;
    const interval = setInterval(() => {
        progress += Math.random() * 15;
        if (progress > 95) {
            clearInterval(interval);
            progress = 95;
        }
        document.getElementById('progress-indicator').style.width = progress + '%';
    }, 200);
    window.currentProgressInterval = interval;
}

// Hide loading state
function hideLoadingState() {
    if (window.currentProgressInterval) {
        clearInterval(window.currentProgressInterval);
    }
    document.getElementById('progress-indicator').style.width = '100%';
    setTimeout(() => {
        document.getElementById('loading-view').classList.add('hidden');
    }, 300);
}

// Show results
function showResults(data) {
    document.getElementById('welcome-view').classList.add('hidden');
    document.getElementById('results-view').classList.remove('hidden');
    
    // Photo
    if (data.photo && data.photo.path) {
        document.getElementById('photo-placeholder').classList.add('hidden');
        const img = document.getElementById('photo-img');
        img.src = `/extracted/${data.request_id}/photo.png`;
        img.classList.remove('hidden');
        
        document.getElementById('photo-conf').textContent = Math.round((data.photo.confidence || 0) * 100) + '%';
        document.getElementById('photo-page').textContent = data.photo.page || 'N/A';
        const bbox = data.photo.bbox || [0,0,0,0];
        document.getElementById('photo-bbox').textContent = `(${bbox[0]}, ${bbox[1]}) - (${bbox[2]}, ${bbox[3]})`;
        
        document.getElementById('photo-dl').href = `/extracted/${data.request_id}/photo.png`;
        document.getElementById('photo-dl').classList.remove('disabled');
    } else {
        document.getElementById('photo-img').classList.add('hidden');
        document.getElementById('photo-placeholder').classList.remove('hidden');
        document.getElementById('photo-dl').classList.add('disabled');
        document.getElementById('photo-conf').textContent = '--%';
        document.getElementById('photo-page').textContent = '--';
        document.getElementById('photo-bbox').textContent = '--';
    }
    
    // Signature
    if (data.signature && data.signature.path) {
        document.getElementById('sig-placeholder').classList.add('hidden');
        const img = document.getElementById('sig-img');
        img.src = `/extracted/${data.request_id}/signature.png`;
        img.classList.remove('hidden');
        
        document.getElementById('sig-conf').textContent = Math.round((data.signature.confidence || 0) * 100) + '%';
        document.getElementById('sig-page').textContent = data.signature.page || 'N/A';
        const bbox = data.signature.bbox || [0,0,0,0];
        document.getElementById('sig-bbox').textContent = `(${bbox[0]}, ${bbox[1]}) - (${bbox[2]}, ${bbox[3]})`;
        
        document.getElementById('sig-dl').href = `/extracted/${data.request_id}/signature.png`;
        document.getElementById('sig-dl').classList.remove('disabled');
    } else {
        document.getElementById('sig-img').classList.add('hidden');
        document.getElementById('sig-placeholder').classList.remove('hidden');
        document.getElementById('sig-dl').classList.add('disabled');
        document.getElementById('sig-conf').textContent = '--%';
        document.getElementById('sig-page').textContent = '--';
        document.getElementById('sig-bbox').textContent = '--';
    }
}

// ------------------------------
// Template Designer
// ------------------------------

function initDesignerListeners() {
    document.getElementById('back-to-dashboard-btn').addEventListener('click', closeTemplateDesigner);
    
    setupDesignerDropzone();
    
    document.getElementById('add-photo-btn').addEventListener('click', () => addNewField('photo'));
    document.getElementById('add-signature-btn').addEventListener('click', () => addNewField('signature'));
    document.getElementById('delete-field-btn').addEventListener('click', deleteSelectedField);
    
    document.getElementById('prev-page-btn').addEventListener('click', () => navigatePage(-1));
    document.getElementById('next-page-btn').addEventListener('click', () => navigatePage(1));
    
    document.getElementById('load-template-btn').addEventListener('click', loadTemplate);
    document.getElementById('save-template-btn').addEventListener('click', saveTemplate);
    
    // Field property inputs
    setupPropertyInputs();
}

// Setup designer dropzone
function setupDesignerDropzone() {
    const dropzone = document.getElementById('designer-form-dropzone');
    const fileInput = document.getElementById('designer-form-pdf');
    const fileInfo = document.getElementById('designer-file-info');

    const preventDefaults = (e) => {
        e.preventDefault();
        e.stopPropagation();
    };

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, preventDefaults, false);
    });

    dropzone.addEventListener('dragover', () => dropzone.classList.add('dragover'), false);
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'), false);
    dropzone.addEventListener('drop', () => dropzone.classList.remove('dragover'), false);

    const handleFile = async (file) => {
        state.designer.pdfData = file;
        fileInfo.textContent = `${file.name} (${formatBytes(file.size)})`;
        fileInfo.classList.add('selected');
        
        await renderFirstPage(file);
    };

    dropzone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            handleFile(files[0]);
        }
    }, false);

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) handleFile(e.target.files[0]);
    });

    const browseBtn = dropzone.querySelector('.browse-btn');
    if (browseBtn) {
        browseBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            fileInput.click();
        });
    }
}

// Render first page of PDF
async function renderFirstPage(file) {
    try {
        const formData = new FormData();
        formData.append('pdf', file);
        formData.append('page', 0);
        
        const res = await fetch('/api/v1/pdf/render-page', {
            method: 'POST',
            body: formData
        });
        
        if (!res.ok) throw new Error('Failed to render page');
        
        // Get page dimensions from headers
        state.designer.pageWidthPts = parseFloat(res.headers.get('X-Page-Width-Points'));
        state.designer.pageHeightPts = parseFloat(res.headers.get('X-Page-Height-Points'));
        state.designer.totalPages = parseInt(res.headers.get('X-Page-Count'));
        state.designer.currentPage = 0;
        
        const blob = await res.blob();
        const imgUrl = URL.createObjectURL(blob);
        
        const img = document.getElementById('pdf-page-image');
        img.src = imgUrl;
        img.style.display = 'block';
        
        // Update page navigation
        document.getElementById('page-indicator').textContent = `Page ${state.designer.currentPage + 1} of ${state.designer.totalPages}`;
        document.getElementById('page-navigation').style.display = 'flex';
        
    } catch (e) {
        console.error(e);
        alert('Failed to render PDF: ' + e.message);
    }
}

// Navigate pages
async function navigatePage(delta) {
    const newPage = state.designer.currentPage + delta;
    if (newPage < 0 || newPage >= state.designer.totalPages) return;
    
    try {
        const formData = new FormData();
        formData.append('pdf', state.designer.pdfData);
        formData.append('page', newPage);
        
        const res = await fetch('/api/v1/pdf/render-page', {
            method: 'POST',
            body: formData
        });
        
        if (!res.ok) throw new Error('Failed to render page');
        
        state.designer.currentPage = newPage;
        state.designer.pageWidthPts = parseFloat(res.headers.get('X-Page-Width-Points'));
        state.designer.pageHeightPts = parseFloat(res.headers.get('X-Page-Height-Points'));
        
        const blob = await res.blob();
        const imgUrl = URL.createObjectURL(blob);
        
        const img = document.getElementById('pdf-page-image');
        img.src = imgUrl;
        
        document.getElementById('page-indicator').textContent = `Page ${state.designer.currentPage + 1} of ${state.designer.totalPages}`;
        
        // Re-render fields for new page
        renderAllFields();
        
    } catch (e) {
        console.error(e);
    }
}

// Add new field
function addNewField(fieldType) {
    if (!state.designer.pdfData) {
        alert('Please upload a PDF first');
        return;
    }

    const id = generateFieldId();
    const defaultWidthPts = fieldType === 'photo' ? 150 : 200;
    const defaultHeightPts = fieldType === 'photo' ? 150 : 60;
    
    const field = {
        id: id,
        type: fieldType,
        name: fieldType === 'photo' ? 'photo' : 'signature',
        page: state.designer.currentPage,
        x: 50,
        y: 50,
        width: defaultWidthPts,
        height: defaultHeightPts,
        required: true
    };
    
    state.designer.fields[id] = field;
    selectField(id);
    renderAllFields();
    updateFieldsList();
}

// Render all fields for current page
function renderAllFields() {
    const container = document.getElementById('canvas-container');
    const img = document.getElementById('pdf-page-image');
    
    // Remove existing field elements except img
    const existingFields = container.querySelectorAll('.field-box');
    existingFields.forEach(el => el.remove());
    
    if (!state.designer.pageWidthPts || !state.designer.pageHeightPts) return;
    
    // Calculate scale factor
    const scaleX = img.clientWidth / state.designer.pageWidthPts;
    const scaleY = img.clientHeight / state.designer.pageHeightPts;
    
    // Render fields for current page
    Object.values(state.designer.fields).filter(f => f.page === state.designer.currentPage).forEach(field => {
        const fieldEl = document.createElement('div');
        fieldEl.className = `field-box ${field.type === 'photo' ? 'photo-field' : 'signature-field'}`;
        if (field.id === state.designer.selectedFieldId) {
            fieldEl.classList.add('selected');
        }
        fieldEl.dataset.fieldId = field.id;
        
        // Convert points to pixels
        const left = field.x * scaleX;
        const top = field.y * scaleY;
        const width = field.width * scaleX;
        const height = field.height * scaleY;
        
        fieldEl.style.left = left + 'px';
        fieldEl.style.top = top + 'px';
        fieldEl.style.width = width + 'px';
        fieldEl.style.height = height + 'px';
        
        // Field label
        const label = document.createElement('div');
        label.className = 'field-label';
        label.textContent = field.name;
        fieldEl.appendChild(label);
        
        // Resize handles
        const handles = ['nw', 'ne', 'sw', 'se', 'n', 's', 'e', 'w'];
        handles.forEach(handle => {
            const handleEl = document.createElement('div');
            handleEl.className = `resize-handle ${handle}`;
            fieldEl.appendChild(handleEl);
        });
        
        // Add event listeners
        fieldEl.addEventListener('mousedown', (e) => {
            if (e.target.classList.contains('resize-handle')) {
                startResize(e, field.id, e.target.classList[1]);
            } else {
                selectField(field.id);
                startDrag(e, field.id);
            }
        });
        
        container.appendChild(fieldEl);
    });
    
    // Re-bind document listeners for drag/resize
    document.onmousemove = handleMouseMove;
    document.onmouseup = handleMouseUp;
}

// Select field
function selectField(id) {
    state.designer.selectedFieldId = id;
    renderAllFields();
    updateFieldsList();
    updatePropertyInputs();
}

// Start drag
function startDrag(e, fieldId) {
    e.preventDefault();
    state.designer.isDragging = true;
    state.designer.dragStartX = e.clientX;
    state.designer.dragStartY = e.clientY;
}

// Start resize
function startResize(e, fieldId, handle) {
    e.preventDefault();
    state.designer.isResizing = true;
    state.designer.selectedFieldId = fieldId;
    state.designer.resizeHandle = handle;
    state.designer.dragStartX = e.clientX;
    state.designer.dragStartY = e.clientY;
}

// Handle mouse move
function handleMouseMove(e) {
    if (!state.designer.isDragging && !state.designer.isResizing) return;
    
    const img = document.getElementById('pdf-page-image');
    const scaleX = img.clientWidth / state.designer.pageWidthPts;
    const scaleY = img.clientHeight / state.designer.pageHeightPts;
    
    const deltaX = (e.clientX - state.designer.dragStartX) / scaleX;
    const deltaY = (e.clientY - state.designer.dragStartY) / scaleY;
    
    const field = state.designer.fields[state.designer.selectedFieldId];
    if (!field) return;
    
    if (state.designer.isDragging) {
        field.x = Math.max(0, field.x + deltaX);
        field.y = Math.max(0, field.y + deltaY);
    } else if (state.designer.isResizing) {
        const handle = state.designer.resizeHandle;
        
        if (handle.includes('n')) {
            const newY = field.y + deltaY;
            const newHeight = field.height - deltaY;
            if (newHeight > 10) {
                field.y = newY;
                field.height = newHeight;
            }
        }
        if (handle.includes('s')) {
            field.height = Math.max(10, field.height + deltaY);
        }
        if (handle.includes('w')) {
            const newX = field.x + deltaX;
            const newWidth = field.width - deltaX;
            if (newWidth > 10) {
                field.x = newX;
                field.width = newWidth;
            }
        }
        if (handle.includes('e')) {
            field.width = Math.max(10, field.width + deltaX);
        }
    }
    
    state.designer.dragStartX = e.clientX;
    state.designer.dragStartY = e.clientY;
    
    renderAllFields();
    updatePropertyInputs();
}

// Handle mouse up
function handleMouseUp() {
    state.designer.isDragging = false;
    state.designer.isResizing = false;
    state.designer.resizeHandle = null;
}

// Delete selected field
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

// Update fields list
function updateFieldsList() {
    const container = document.getElementById('fields-list-container');
    const fields = Object.values(state.designer.fields);
    
    if (fields.length === 0) {
        container.innerHTML = '<p class="input-hint" style="margin: 8px 0;">No fields added yet</p>';
        return;
    }
    
    container.innerHTML = '';
    
    fields.forEach(field => {
        const el = document.createElement('div');
        el.className = `field-list-item ${field.id === state.designer.selectedFieldId ? 'selected' : ''}`;
        
        el.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; flex-grow: 1;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div class="field-type-badge ${field.type}">
                        ${field.type === 'photo' ? 'P' : 'S'}
                    </div>
                    <div style="font-weight: 500;">${field.name}</div>
                </div>
                <div style="color: var(--text-muted); font-size: 0.875rem;">Page ${field.page + 1}</div>
            </div>
        `;
        
        el.addEventListener('click', () => selectField(field.id));
        container.appendChild(el);
    });
}

// Setup property inputs
function setupPropertyInputs() {
    ['name', 'page', 'x', 'y', 'width', 'height'].forEach(key => {
        const input = document.getElementById(`field-${key}-input`);
        if (input) {
            input.addEventListener('input', () => updateFieldFromProperty(key, input.value));
        }
    });
}

// Update property inputs
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

// Update field from property input
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

// Load template
async function loadTemplate() {
    const templateName = prompt('Enter template name to load:');
    if (!templateName) return;
    
    try {
        const res = await fetch(`/api/v1/templates/${templateName}`);
        if (!res.ok) throw new Error('Template not found');
        
        const data = await res.json();
        state.designer.templateName = templateName;
        state.designer.templateDesc = data.template.description || '';
        state.designer.fields = {};
        
        // Convert template fields to designer fields
        Object.entries(data.template.fields || {}).forEach(([name, f]) => {
            const id = generateFieldId();
            state.designer.fields[id] = {
                id: id,
                type: name.toLowerCase().includes('photo') ? 'photo' : 'signature',
                name: name,
                page: f.page,
                x: f.x,
                y: f.y,
                width: f.width,
                height: f.height,
                required: f.required ?? true
            };
        });
        
        document.getElementById('template-name-input').value = state.designer.templateName;
        document.getElementById('template-desc-input').value = state.designer.templateDesc;
        
        renderAllFields();
        updateFieldsList();
        
        alert('Template loaded successfully!');
    } catch (e) {
        console.error(e);
        alert('Failed to load template: ' + e.message);
    }
}

// Save template
async function saveTemplate() {
    const templateName = document.getElementById('template-name-input').value.trim();
    if (!templateName) {
        alert('Please enter a template name');
        return;
    }
    
    if (Object.keys(state.designer.fields).length === 0) {
        alert('Please add at least one field');
        return;
    }
    
    try {
        // Build template data
        const templateData = {
            name: templateName,
            description: document.getElementById('template-desc-input').value,
            fields: {}
        };
        
        Object.values(state.designer.fields).forEach(f => {
            templateData.fields[f.name] = {
                page: f.page,
                x: f.x,
                y: f.y,
                width: f.width,
                height: f.height,
                required: f.required
            };
        });
        
        const res = await fetch(`/api/v1/templates/${encodeURIComponent(templateName)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(templateData)
        });
        
        if (!res.ok) {
            throw new Error('Failed to save template');
        }
        
        alert('Template saved successfully!');
    } catch (e) {
        console.error(e);
        alert('Failed to save template: ' + e.message);
    }
}
