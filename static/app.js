document.addEventListener('DOMContentLoaded', () => {
    // API Endpoints
    const API_BASE = '/api/v1';
    const ENDPOINTS = {
        health: `${API_BASE}/health`,
        templates: `${API_BASE}/templates`,
        extract: `${API_BASE}/extract`,
        process: `${API_BASE}/process`,
        renderPage: `${API_BASE}/pdf/render-page`
    };

    // UI Elements - Dashboard
    const healthBadge = document.getElementById('health-badge');
    const healthText = document.getElementById('health-text');
    const templateSelect = document.getElementById('template_name');
    const templateDesc = document.getElementById('template-desc');
    const processingForm = document.getElementById('processing-form');
    const sourcePdfInput = document.getElementById('source_pdf');
    const formPdfInput = document.getElementById('form_pdf');
    const sourceDropzone = document.getElementById('source-dropzone');
    const formDropzone = document.getElementById('form-dropzone');
    const sourceFileInfo = document.getElementById('source-file-info');
    const formFileInfo = document.getElementById('form-file-info');
    const extractBtn = document.getElementById('extract-btn');
    const processBtn = document.getElementById('process-btn');
    const welcomeView = document.getElementById('welcome-view');
    const loadingView = document.getElementById('loading-view');
    const resultsView = document.getElementById('results-view');
    const loadingTitle = document.getElementById('loading-title');
    const loadingDesc = document.getElementById('loading-desc');
    const progressIndicator = document.getElementById('progress-indicator');
    const photoImg = document.getElementById('photo-img');
    const photoPlaceholder = document.getElementById('photo-placeholder');
    const photoConf = document.getElementById('photo-conf');
    const photoPage = document.getElementById('photo-page');
    const photoBbox = document.getElementById('photo-bbox');
    const photoDl = document.getElementById('photo-dl');
    const sigImg = document.getElementById('sig-img');
    const sigPlaceholder = document.getElementById('sig-placeholder');
    const sigConf = document.getElementById('sig-conf');
    const sigPage = document.getElementById('sig-page');
    const sigBbox = document.getElementById('sig-bbox');
    const sigDl = document.getElementById('sig-dl');
    const pdfOutputCard = document.getElementById('pdf-output-card');
    const pdfIframe = document.getElementById('pdf-iframe');
    const pdfViewBtn = document.getElementById('pdf-view-btn');
    const pdfDownloadBtn = document.getElementById('pdf-download-btn');
    const dashboardView = document.getElementById('dashboard-view');
    const designTemplateBtn = document.getElementById('design-template-btn');

    // UI Elements - Template Designer
    const templateDesignerView = document.getElementById('template-designer-view');
    const backToDashboardBtn = document.getElementById('back-to-dashboard-btn');
    const designerFormDropzone = document.getElementById('designer-form-dropzone');
    const designerFormPdf = document.getElementById('designer-form-pdf');
    const pageNavigation = document.getElementById('page-navigation');
    const prevPageBtn = document.getElementById('prev-page-btn');
    const nextPageBtn = document.getElementById('next-page-btn');
    const pageIndicator = document.getElementById('page-indicator');
    const pdfPageImage = document.getElementById('pdf-page-image');
    const canvasContainer = document.getElementById('canvas-container');
    const addPhotoBtn = document.getElementById('add-photo-btn');
    const addSignatureBtn = document.getElementById('add-signature-btn');
    const deleteFieldBtn = document.getElementById('delete-field-btn');
    const templateNameInput = document.getElementById('template-name-input');
    const templateDescInput = document.getElementById('template-desc-input');
    const fieldProperties = document.getElementById('field-properties');
    const fieldNameInput = document.getElementById('field-name-input');
    const fieldPageInput = document.getElementById('field-page-input');
    const fieldXInput = document.getElementById('field-x-input');
    const fieldYInput = document.getElementById('field-y-input');
    const fieldWidthInput = document.getElementById('field-width-input');
    const fieldHeightInput = document.getElementById('field-height-input');
    const fieldsListContainer = document.getElementById('fields-list-container');
    const loadTemplateBtn = document.getElementById('load-template-btn');
    const saveTemplateBtn = document.getElementById('save-template-btn');

    // State Variables - Dashboard
    let templatesData = [];

    // State Variables - Template Designer
    let designerState = {
        currentPage: 0,
        totalPages: 0,
        pdfFile: null,
        pageWidthPoints: 0,
        pageHeightPoints: 0,
        fields: {},
        selectedFieldId: null,
        templateName: '',
        templateDescription: ''
    };

    // --- 1. Startup Checks ---
    checkSystemHealth();
    loadTemplates();

    // --- 2. Health & Templates Fetching ---
    async function checkSystemHealth() {
        try {
            const res = await fetch(ENDPOINTS.health);
            if (!res.ok) throw new Error('Unhealthy');
            const data = await res.json();
            
            healthBadge.className = 'badge badge-online';
            healthText.textContent = `Server Online (v${data.version})`;
        } catch (err) {
            healthBadge.className = 'badge badge-offline';
            healthText.textContent = 'Server Offline';
            showToast('Cannot connect to PDF completion backend.', 'error');
        }
    }

    async function loadTemplates() {
        try {
            const res = await fetch(ENDPOINTS.templates);
            if (!res.ok) throw new Error('Failed to load templates');
            const data = await res.json();
            
            templatesData = data.templates;
            templateSelect.innerHTML = '';
            
            if (templatesData.length === 0) {
                templateSelect.innerHTML = '<option value="" disabled selected>No templates configured</option>';
                return;
            }

            // Populate select dropdown
            templatesData.forEach((tmpl, index) => {
                const opt = document.createElement('option');
                opt.value = tmpl.name;
                opt.textContent = tmpl.name.replace(/_/g, ' ');
                if (index === 0) opt.selected = true;
                templateSelect.appendChild(opt);
            });

            // Trigger description update
            updateTemplateInfo();
        } catch (err) {
            templateSelect.innerHTML = '<option value="" disabled selected>Failed to load schemas</option>';
            showToast('Error loading form templates.', 'error');
        }
    }

    function updateTemplateInfo() {
        const selectedName = templateSelect.value;
        const template = templatesData.find(t => t.name === selectedName);
        if (template) {
            templateDesc.textContent = `${template.description || 'No description'} — Fields: ${template.fields.join(', ')}`;
        }
    }

    templateSelect.addEventListener('change', updateTemplateInfo);

    // --- 3. Drag and Drop File Handlers ---
    function setupDropzone(dropzone, input, infoSpan) {
        // Prevent defaults
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        // Highlight classes
        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, () => dropzone.classList.add('dragover'), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, () => dropzone.classList.remove('dragover'), false);
        });

        // Drop file
        dropzone.addEventListener('drop', e => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files.length > 0) {
                input.files = files;
                updateFileInfo(files[0], infoSpan);
            }
        });

        // Click to open file dialog
        dropzone.addEventListener('click', () => {
            input.click();
        });

        // Input change
        input.addEventListener('change', () => {
            if (input.files.length > 0) {
                updateFileInfo(input.files[0], infoSpan);
            }
        });
    }

    function updateFileInfo(file, infoSpan) {
        if (file) {
            const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
            infoSpan.textContent = `${file.name} (${sizeMB} MB)`;
        } else {
            infoSpan.textContent = 'No file selected';
        }
    }

    setupDropzone(sourceDropzone, sourcePdfInput, sourceFileInfo);
    setupDropzone(formDropzone, formPdfInput, formFileInfo);
    setupDropzone(designerFormDropzone, designerFormPdf, null);

    // --- 4. Form Actions (Extract & Fill) ---
    
    // Extract Only button click handler
    extractBtn.addEventListener('click', async () => {
        if (!sourcePdfInput.files[0]) {
            showToast('Please select a scanned document PDF first.', 'error');
            return;
        }

        showLoading('Extracting Components...', 'Running computer vision algorithms to locate photo and signature.');
        animateProgressBar(90, 1500);

        const formData = new FormData();
        formData.append('source_pdf', sourcePdfInput.files[0]);

        try {
            const res = await fetch(ENDPOINTS.extract, {
                method: 'POST',
                body: formData
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || 'Extraction failed');
            }

            const data = await res.json();
            displayExtractionResults(data);
            pdfOutputCard.classList.add('hidden'); // Hide PDF card since it's extract-only
            showToast('Photo and signature extracted successfully!', 'success');
        } catch (err) {
            showToast(err.message, 'error');
            showView('welcome');
        }
    });

    // Form submit handler (Auto-Fill Process)
    processingForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        if (!sourcePdfInput.files[0]) {
            showToast('Please upload a scanned document PDF.', 'error');
            return;
        }
        if (!formPdfInput.files[0]) {
            showToast('Please upload a blank form template PDF.', 'error');
            return;
        }
        if (!templateSelect.value) {
            showToast('Please select a target layout template.', 'error');
            return;
        }

        showLoading('Auto-Filling Form PDF...', 'Cropping features and compiling them into the template layout.');
        animateProgressBar(60, 1200);

        // We run extract and fill in parallel or sequential.
        // First we call extract to render previews in the UI.
        const extractFormData = new FormData();
        extractFormData.append('source_pdf', sourcePdfInput.files[0]);

        const processFormData = new FormData();
        processFormData.append('source_pdf', sourcePdfInput.files[0]);
        processFormData.append('form_pdf', formPdfInput.files[0]);
        processFormData.append('template_name', templateSelect.value);

        try {
            // Step 1: Request extraction coordinates for previews
            const extractPromise = fetch(ENDPOINTS.extract, {
                method: 'POST',
                body: extractFormData
            }).then(r => r.ok ? r.json() : null);

            // Step 2: Request PDF processing
            const processPromise = fetch(ENDPOINTS.process, {
                method: 'POST',
                body: processFormData
            });

            const [extractData, processRes] = await Promise.all([extractPromise, processPromise]);

            if (!processRes.ok) {
                const errData = await processRes.json();
                throw new Error(errData.detail || 'Form filling failed');
            }

            // Set progress to 100
            progressIndicator.style.width = '100%';

            // Parse completed PDF binary
            const pdfBlob = await processRes.blob();
            const pdfUrl = URL.createObjectURL(pdfBlob);

            // Display results
            if (extractData) {
                displayExtractionResults(extractData);
            }
            displayPdfResult(pdfUrl, templateSelect.value);
            showToast('Document generated successfully!', 'success');
        } catch (err) {
            showToast(err.message, 'error');
            showView('welcome');
        }
    });

    // --- 5. Presentation & View Utilities ---
    function showView(viewName) {
        welcomeView.classList.add('hidden');
        loadingView.classList.add('hidden');
        resultsView.classList.add('hidden');

        if (viewName === 'welcome') {
            welcomeView.classList.remove('hidden');
        } else if (viewName === 'loading') {
            loadingView.classList.remove('hidden');
        } else if (viewName === 'results') {
            resultsView.classList.remove('hidden');
        }
    }

    function showLoading(title, desc) {
        loadingTitle.textContent = title;
        loadingDesc.textContent = desc;
        progressIndicator.style.width = '0%';
        showView('loading');
    }

    function animateProgressBar(targetWidth, duration) {
        let current = 0;
        const stepTime = 50;
        const steps = duration / stepTime;
        const increment = targetWidth / steps;

        const interval = setInterval(() => {
            current += increment;
            if (current >= targetWidth) {
                progressIndicator.style.width = `${targetWidth}%`;
                clearInterval(interval);
            } else {
                progressIndicator.style.width = `${current}%`;
            }
        }, stepTime);
    }

    function getWebPath(absolutePath) {
        if (!absolutePath) return '';
        const normalized = absolutePath.replace(/\\/g, '/');
        const marker = '/extracted/';
        const index = normalized.indexOf(marker);
        if (index !== -1) {
            return normalized.substring(index);
        }
        return normalized;
    }

    function displayExtractionResults(data) {
        showView('results');

        // Render Photo
        if (data.photo && data.photo.found) {
            photoImg.src = getWebPath(data.photo.path);
            photoImg.classList.remove('hidden');
            photoPlaceholder.classList.add('hidden');
            
            const confPct = Math.round(data.photo.confidence * 100);
            photoConf.textContent = `${confPct}%`;
            photoConf.className = `conf-badge ${getConfidenceClass(data.photo.confidence)}`;
            
            photoPage.textContent = data.photo.page + 1; // 0-indexed to 1-indexed for operator
            photoBbox.textContent = JSON.stringify(data.photo.bbox);
            
            photoDl.href = getWebPath(data.photo.path);
            photoDl.classList.remove('disabled');
        } else {
            photoImg.classList.add('hidden');
            photoPlaceholder.classList.remove('hidden');
            photoConf.textContent = '0%';
            photoConf.className = 'conf-badge badge-offline';
            photoPage.textContent = 'Not found';
            photoBbox.textContent = 'None';
            photoDl.classList.add('disabled');
        }

        // Render Signature
        if (data.signature && data.signature.found) {
            sigImg.src = getWebPath(data.signature.path);
            sigImg.classList.remove('hidden');
            sigPlaceholder.classList.add('hidden');
            
            const confPct = Math.round(data.signature.confidence * 100);
            sigConf.textContent = `${confPct}%`;
            sigConf.className = `conf-badge ${getConfidenceClass(data.signature.confidence)}`;
            
            sigPage.textContent = data.signature.page + 1; // 0-indexed to 1-indexed
            sigBbox.textContent = JSON.stringify(data.signature.bbox);
            
            sigDl.href = getWebPath(data.signature.path);
            sigDl.classList.remove('disabled');
        } else {
            sigImg.classList.add('hidden');
            sigPlaceholder.classList.remove('hidden');
            sigConf.textContent = '0%';
            sigConf.className = 'conf-badge badge-offline';
            sigPage.textContent = 'Not found';
            sigBbox.textContent = 'None';
            sigDl.classList.add('disabled');
        }
    }

    function getConfidenceClass(conf) {
        if (conf >= 0.75) return 'badge-online';     // green
        if (conf >= 0.40) return 'badge-warning';    // amber
        return 'badge-offline';                      // red
    }

    function displayPdfResult(objectUrl, templateName) {
        pdfOutputCard.classList.remove('hidden');
        pdfIframe.src = objectUrl;
        
        pdfViewBtn.href = objectUrl;
        pdfDownloadBtn.href = objectUrl;
        pdfDownloadBtn.download = `completed_${templateName}_${Date.now()}.pdf`;
    }

    // Toast Notification System
    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        // Add matching icon
        let icon = '';
        if (type === 'error') {
            icon = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
        } else if (type === 'success') {
            icon = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>';
        } else {
            icon = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>';
        }

        toast.innerHTML = `${icon} <span>${message}</span>`;
        document.body.appendChild(toast);

        // Show toast
        setTimeout(() => toast.classList.add('show'), 10);

        // Hide and remove toast
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    // --- 6. Template Designer ---

    // Toggle between dashboard and designer
    designTemplateBtn.addEventListener('click', () => {
        dashboardView.classList.add('hidden');
        templateDesignerView.classList.remove('hidden');
    });

    backToDashboardBtn.addEventListener('click', () => {
        templateDesignerView.classList.add('hidden');
        dashboardView.classList.remove('hidden');
        loadTemplates(); // Refresh templates list
    });

    // Handle PDF upload in designer
    designerFormPdf.addEventListener('change', async (e) => {
        if (e.target.files.length > 0) {
            designerState.pdfFile = e.target.files[0];
            await loadPdfPage(0);
        }
    });

    // Load PDF page
    async function loadPdfPage(pageIndex) {
        if (!designerState.pdfFile) return;

        const formData = new FormData();
        formData.append('pdf_file', designerState.pdfFile);
        formData.append('page_index', pageIndex);

        try {
            const res = await fetch(ENDPOINTS.renderPage, {
                method: 'POST',
                body: formData
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || 'Failed to render page');
            }

            // Get page dimensions from headers
            designerState.pageWidthPoints = parseFloat(res.headers.get('X-Page-Width-Points'));
            designerState.pageHeightPoints = parseFloat(res.headers.get('X-Page-Height-Points'));
            designerState.totalPages = parseInt(res.headers.get('X-Page-Count'));
            designerState.currentPage = pageIndex;

            // Update page navigation
            pageNavigation.style.display = 'flex';
            pageIndicator.textContent = `Page ${pageIndex + 1} of ${designerState.totalPages}`;
            prevPageBtn.disabled = pageIndex === 0;
            nextPageBtn.disabled = pageIndex === designerState.totalPages - 1;

            // Render image
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            pdfPageImage.src = url;
            pdfPageImage.style.display = 'block';

            // Render fields for this page
            renderFields();
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    // Page navigation
    prevPageBtn.addEventListener('click', () => {
        if (designerState.currentPage > 0) {
            loadPdfPage(designerState.currentPage - 1);
        }
    });

    nextPageBtn.addEventListener('click', () => {
        if (designerState.currentPage < designerState.totalPages - 1) {
            loadPdfPage(designerState.currentPage + 1);
        }
    });

    // Add field handlers
    addPhotoBtn.addEventListener('click', () => addNewField('photo'));
    addSignatureBtn.addEventListener('click', () => addNewField('signature'));

    function addNewField(type) {
        if (!designerState.pdfFile) {
            showToast('Please upload a PDF first.', 'error');
            return;
        }

        const id = `field_${Date.now()}`;
        const defaultWidth = type === 'photo' ? 100 : 150;
        const defaultHeight = type === 'photo' ? 120 : 50;

        designerState.fields[id] = {
            id,
            name: type === 'photo' ? `photo_${Object.keys(designerState.fields).length + 1}` : `signature_${Object.keys(designerState.fields).length + 1}`,
            type,
            page: designerState.currentPage,
            x: 50,
            y: 50,
            width: defaultWidth,
            height: defaultHeight,
            required: true
        };

        selectField(id);
        renderFields();
        updateFieldsList();
    }

    // Render fields on canvas
    function renderFields() {
        // Clear existing fields
        const existingFields = canvasContainer.querySelectorAll('.field-box');
        existingFields.forEach(el => el.remove());

        // Get image dimensions for scaling
        const imgRect = pdfPageImage.getBoundingClientRect();
        const imgWidth = imgRect.width;
        const imgHeight = imgRect.height;
        const scaleX = imgWidth / designerState.pageWidthPoints;
        const scaleY = imgHeight / designerState.pageHeightPoints;

        // Render fields for current page
        Object.values(designerState.fields).forEach(field => {
            if (field.page !== designerState.currentPage) return;

            const fieldEl = document.createElement('div');
            fieldEl.className = `field-box ${field.type}-field ${designerState.selectedFieldId === field.id ? 'selected' : ''}`;
            fieldEl.dataset.fieldId = field.id;

            // Calculate position and size in pixels
            const left = field.x * scaleX;
            const top = field.y * scaleY;
            const width = field.width * scaleX;
            const height = field.height * scaleY;

            fieldEl.style.left = `${left}px`;
            fieldEl.style.top = `${top}px`;
            fieldEl.style.width = `${width}px`;
            fieldEl.style.height = `${height}px`;

            // Add field label
            const label = document.createElement('div');
            label.className = 'field-label';
            label.textContent = field.name;
            fieldEl.appendChild(label);

            // Add resize handles
            const handles = ['top-left', 'top-right', 'bottom-left', 'bottom-right'];
            handles.forEach(handleType => {
                const handle = document.createElement('div');
                handle.className = `resize-handle ${handleType}`;
                handle.dataset.handle = handleType;
                fieldEl.appendChild(handle);
            });

            // Add click handler
            fieldEl.addEventListener('mousedown', (e) => {
                if (e.target.classList.contains('resize-handle')) return;
                selectField(field.id);
                startDragging(e, field.id);
            });

            // Add resize handlers
            fieldEl.querySelectorAll('.resize-handle').forEach(handle => {
                handle.addEventListener('mousedown', (e) => {
                    e.stopPropagation();
                    selectField(field.id);
                    startResizing(e, field.id, handle.dataset.handle);
                });
            });

            canvasContainer.appendChild(fieldEl);
        });
    }

    // Select field
    function selectField(fieldId) {
        designerState.selectedFieldId = fieldId;
        renderFields();
        updateFieldsList();
        updateFieldProperties();
    }

    // Update fields list
    function updateFieldsList() {
        fieldsListContainer.innerHTML = '';
        const fields = Object.values(designerState.fields);
        
        if (fields.length === 0) {
            fieldsListContainer.innerHTML = '<p class="input-hint" style="margin: 8px 0;">No fields added yet</p>';
            return;
        }

        fields.forEach(field => {
            const item = document.createElement('div');
            item.className = `field-list-item ${designerState.selectedFieldId === field.id ? 'selected' : ''}`;
            item.innerHTML = `
                <div class="field-list-item-name">
                    <span class="field-type-badge ${field.type}">${field.type}</span>
                    <span>${field.name}</span>
                </div>
                <span style="font-size: 0.75rem; color: var(--text-muted);">Pg ${field.page + 1}</span>
            `;
            item.addEventListener('click', () => {
                if (field.page !== designerState.currentPage) {
                    loadPdfPage(field.page);
                }
                selectField(field.id);
            });
            fieldsListContainer.appendChild(item);
        });
    }

    // Update field properties panel
    function updateFieldProperties() {
        if (!designerState.selectedFieldId) {
            fieldProperties.style.display = 'none';
            return;
        }

        const field = designerState.fields[designerState.selectedFieldId];
        if (!field) return;

        fieldProperties.style.display = 'flex';
        fieldProperties.style.flexDirection = 'column';
        fieldProperties.style.gap = '12px';

        fieldNameInput.value = field.name;
        fieldPageInput.value = field.page;
        fieldXInput.value = field.x.toFixed(1);
        fieldYInput.value = field.y.toFixed(1);
        fieldWidthInput.value = field.width.toFixed(1);
        fieldHeightInput.value = field.height.toFixed(1);
    }

    // Handle property changes
    fieldNameInput.addEventListener('input', () => {
        if (designerState.selectedFieldId) {
            designerState.fields[designerState.selectedFieldId].name = fieldNameInput.value;
            renderFields();
            updateFieldsList();
        }
    });

    fieldPageInput.addEventListener('input', () => {
        if (designerState.selectedFieldId) {
            const newPage = parseInt(fieldPageInput.value);
            if (!isNaN(newPage) && newPage >= 0 && newPage < designerState.totalPages) {
                designerState.fields[designerState.selectedFieldId].page = newPage;
                renderFields();
                updateFieldsList();
            }
        }
    });

    fieldXInput.addEventListener('input', () => {
        if (designerState.selectedFieldId) {
            const val = parseFloat(fieldXInput.value);
            if (!isNaN(val) && val >= 0) {
                designerState.fields[designerState.selectedFieldId].x = val;
                renderFields();
            }
        }
    });

    fieldYInput.addEventListener('input', () => {
        if (designerState.selectedFieldId) {
            const val = parseFloat(fieldYInput.value);
            if (!isNaN(val) && val >= 0) {
                designerState.fields[designerState.selectedFieldId].y = val;
                renderFields();
            }
        }
    });

    fieldWidthInput.addEventListener('input', () => {
        if (designerState.selectedFieldId) {
            const val = parseFloat(fieldWidthInput.value);
            if (!isNaN(val) && val > 0) {
                designerState.fields[designerState.selectedFieldId].width = val;
                renderFields();
            }
        }
    });

    fieldHeightInput.addEventListener('input', () => {
        if (designerState.selectedFieldId) {
            const val = parseFloat(fieldHeightInput.value);
            if (!isNaN(val) && val > 0) {
                designerState.fields[designerState.selectedFieldId].height = val;
                renderFields();
            }
        }
    });

    // Delete field
    deleteFieldBtn.addEventListener('click', () => {
        if (!designerState.selectedFieldId) {
            showToast('Please select a field first.', 'error');
            return;
        }
        delete designerState.fields[designerState.selectedFieldId];
        designerState.selectedFieldId = null;
        renderFields();
        updateFieldsList();
        updateFieldProperties();
    });

    // Drag and drop logic
    let dragState = null;

    function startDragging(e, fieldId) {
        const imgRect = pdfPageImage.getBoundingClientRect();
        const scaleX = designerState.pageWidthPoints / imgRect.width;
        const scaleY = designerState.pageHeightPoints / imgRect.height;

        dragState = {
            type: 'drag',
            fieldId,
            startX: e.clientX,
            startY: e.clientY,
            initialX: designerState.fields[fieldId].x,
            initialY: designerState.fields[fieldId].y,
            scaleX,
            scaleY
        };

        document.addEventListener('mousemove', onDrag);
        document.addEventListener('mouseup', stopDrag);
    }

    function onDrag(e) {
        if (!dragState) return;

        const dx = (e.clientX - dragState.startX) * dragState.scaleX;
        const dy = (e.clientY - dragState.startY) * dragState.scaleY;

        designerState.fields[dragState.fieldId].x = Math.max(0, dragState.initialX + dx);
        designerState.fields[dragState.fieldId].y = Math.max(0, dragState.initialY + dy);

        renderFields();
        updateFieldProperties();
    }

    function stopDrag() {
        dragState = null;
        document.removeEventListener('mousemove', onDrag);
        document.removeEventListener('mouseup', stopDrag);
    }

    // Resize logic
    function startResizing(e, fieldId, handleType) {
        const imgRect = pdfPageImage.getBoundingClientRect();
        const scaleX = designerState.pageWidthPoints / imgRect.width;
        const scaleY = designerState.pageHeightPoints / imgRect.height;

        dragState = {
            type: 'resize',
            fieldId,
            handleType,
            startX: e.clientX,
            startY: e.clientY,
            initialX: designerState.fields[fieldId].x,
            initialY: designerState.fields[fieldId].y,
            initialWidth: designerState.fields[fieldId].width,
            initialHeight: designerState.fields[fieldId].height,
            scaleX,
            scaleY
        };

        document.addEventListener('mousemove', onResize);
        document.addEventListener('mouseup', stopResize);
    }

    function onResize(e) {
        if (!dragState) return;

        const dx = (e.clientX - dragState.startX) * dragState.scaleX;
        const dy = (e.clientY - dragState.startY) * dragState.scaleY;
        const field = designerState.fields[dragState.fieldId];

        switch (dragState.handleType) {
            case 'top-left':
                field.x = Math.max(0, dragState.initialX + dx);
                field.y = Math.max(0, dragState.initialY + dy);
                field.width = Math.max(10, dragState.initialWidth - dx);
                field.height = Math.max(10, dragState.initialHeight - dy);
                break;
            case 'top-right':
                field.y = Math.max(0, dragState.initialY + dy);
                field.width = Math.max(10, dragState.initialWidth + dx);
                field.height = Math.max(10, dragState.initialHeight - dy);
                break;
            case 'bottom-left':
                field.x = Math.max(0, dragState.initialX + dx);
                field.width = Math.max(10, dragState.initialWidth - dx);
                field.height = Math.max(10, dragState.initialHeight + dy);
                break;
            case 'bottom-right':
                field.width = Math.max(10, dragState.initialWidth + dx);
                field.height = Math.max(10, dragState.initialHeight + dy);
                break;
        }

        renderFields();
        updateFieldProperties();
    }

    function stopResize() {
        dragState = null;
        document.removeEventListener('mousemove', onResize);
        document.removeEventListener('mouseup', stopResize);
    }

    // Load template
    loadTemplateBtn.addEventListener('click', async () => {
        if (templatesData.length === 0) {
            showToast('No templates available to load.', 'error');
            return;
        }

        // For simplicity, load the first template
        // In a real app, you'd show a dialog to select which one to load
        const templateToLoad = templatesData[0];
        
        // Fetch the template data (the templates endpoint gives us field names but not the full definition)
        // So we need to reconstruct from the template data we have
        showToast(`Loading template: ${templateToLoad.name}`, 'info');
        
        designerState.templateName = templateToLoad.name;
        designerState.templateDescription = templateToLoad.description;
        templateNameInput.value = templateToLoad.name;
        templateDescInput.value = templateToLoad.description;
        
        // For this example, we'll clear existing fields and add sample ones
        // In a real app, you'd store the full field definitions somewhere
        showToast('Please re-upload the PDF and adjust the fields as needed.', 'info');
        designerState.fields = {};
        designerState.selectedFieldId = null;
        renderFields();
        updateFieldsList();
        updateFieldProperties();
    });

    // Save template
    saveTemplateBtn.addEventListener('click', async () => {
        const name = templateNameInput.value.trim();
        if (!name) {
            showToast('Please enter a template name.', 'error');
            return;
        }

        if (Object.keys(designerState.fields).length === 0) {
            showToast('Please add at least one field.', 'error');
            return;
        }

        const formData = new FormData();
        formData.append('description', templateDescInput.value.trim());
        formData.append('page_size', 'A4');
        
        // Prepare fields data
        const fieldsData = {};
        Object.values(designerState.fields).forEach(field => {
            fieldsData[field.name] = {
                page: field.page,
                x: field.x,
                y: field.y,
                width: field.width,
                height: field.height,
                required: field.required
            };
        });
        formData.append('fields', JSON.stringify(fieldsData));

        try {
            const res = await fetch(`${ENDPOINTS.templates}/${name}`, {
                method: 'POST',
                body: formData
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || 'Failed to save template');
            }

            showToast(`Template "${name}" saved successfully!`, 'success');
        } catch (err) {
            showToast(err.message, 'error');
        }
    });

    // Re-render fields when window resizes
    window.addEventListener('resize', () => {
        if (designerState.pdfFile) {
            renderFields();
        }
    });
});