    // ── LOADING UTILITIES ─────────────────────────────────────────────────
    function setLoading(btn, isLoading) {
        if (!btn) return;
        if (isLoading) {
            btn.dataset.originalHtml = btn.innerHTML;
            btn.innerHTML = '<div class="btn-dots"><div class="btn-dot"></div><div class="btn-dot"></div><div class="btn-dot"></div></div>';
            btn.disabled = true;
        } else {
            btn.innerHTML = btn.dataset.originalHtml ?? btn.innerHTML;
            btn.disabled = false;
            lucide.createIcons({ nodes: [btn] });
        }
    }

    function startNavBar(e) {
        const bar = document.getElementById('nav-bar');
        if (!bar) return;
        e.preventDefault();
        const href = e.currentTarget.getAttribute('href');
        bar.style.width = '85%';
        setTimeout(() => { window.location.href = href; }, 150);
    }

    // ── STATE ─────────────────────────────────────────────────────────────
    let selectedFiles = [];
    let sessionId = null;
    let printerData = [];
    let serialMap = {};
    let extraColumnsVisible = false;
    let currentStep = 1;
    let contractFilter = 'all';

    const PANELS = ['panel-upload', 'panel-select', 'panel-results', 'panel-contracts'];
    const STEP_TITLES = {
        'panel-upload':    'Nahrát soubory',
        'panel-select':    'Vybrat tiskárny',
        'panel-results':   'Výsledky',
        'panel-contracts': 'Správa smluv',
    };

    // ── DOM REFS ──────────────────────────────────────────────────────────
    const fileInput        = document.getElementById('fileInput');
    const selectedFilesDiv = document.getElementById('selectedFiles');
    const processBtn       = document.getElementById('processBtn');
    const uploadSection    = document.getElementById('uploadSection');
    const loadingDiv       = document.getElementById('loading');
    const errorMessage     = document.getElementById('errorMessage');
    const errorText        = document.getElementById('errorText');

    // ── INIT ──────────────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', () => {
        lucide.createIcons();
        showPanel('panel-upload');
        setStep(1);
        document.querySelectorAll('a[href]').forEach(a => {
            const href = a.getAttribute('href');
            if (href && !href.startsWith('#') && !href.startsWith('javascript')) {
                a.addEventListener('click', startNavBar);
            }
        });
    });

    // ── PANEL MANAGEMENT ──────────────────────────────────────────────────
    function showPanel(id) {
        PANELS.forEach(p => {
            const el = document.getElementById(p);
            el.classList.toggle('hidden', p !== id);
            if (p === id) {
                el.classList.add('panel-enter');
                setTimeout(() => el.classList.remove('panel-enter'), 400);
            }
        });
        document.getElementById('topBarTitle').textContent = STEP_TITLES[id] || '';
    }

    // ── SIDEBAR STEP MANAGEMENT ───────────────────────────────────────────
    function setStep(n) {
        currentStep = n;
        document.getElementById('stepBadge').textContent = `Krok ${n} / 4`;

        for (let i = 1; i <= 4; i++) {
            const btn   = document.getElementById('nav-' + i);
            const badge = document.getElementById('badge-' + i);
            const label = document.getElementById('nav-label-' + i);

            // Reset
            btn.className = 'step-item';

            if (i < n) {
                // Done
                btn.classList.add('opacity-80');
                badge.className = 'step-badge badge-done';
                badge.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';
                label.style.color = '#6ee7b7';
                label.style.fontWeight = '600';
                btn.disabled = false;
            } else if (i === n) {
                // Active
                btn.classList.add('step-active');
                badge.className = 'step-badge badge-active';
                badge.textContent = i;
                label.style.color = '#fff';
                label.style.fontWeight = '700';
                btn.disabled = false;
            } else {
                // Pending
                btn.disabled = true;
                badge.className = 'step-badge badge-pending';
                badge.textContent = i;
                label.style.color = 'rgba(255,255,255,0.3)';
                label.style.fontWeight = '500';
            }
        }
        // Reset contracts nav highlight when returning to step panels
        const navContracts = document.getElementById('nav-contracts');
        if (navContracts) {
            navContracts.style.background = '';
            navContracts.querySelector('.sb-label').style.color = 'rgba(255,255,255,.55)';
        }
    }

    function handleNavClick(n) {
        if (n > currentStep) return;
        if (n === 1) showPanel('panel-upload');
        else if (n === 2) showPanel('panel-select');
        else if (n >= 3) showPanel('panel-results');
        document.getElementById('topBarTitle').textContent = ['', 'Nahrát soubory', 'Vybrat tiskárny', 'Generovat výkaz', 'Stáhnout výsledky'][n];
    }

    // ── TOASTS ────────────────────────────────────────────────────────────
    function showToast(message, type = 'info') {
        const icons  = { success: 'check-circle', error: 'x-circle', info: 'info', warning: 'alert-triangle' };
        const colors = {
            success: { border: '#22c55e', icon: '#86efac' },
            error:   { border: '#ef4444', icon: '#fca5a5' },
            info:    { border: '#6366f1', icon: '#a5b4fc' },
            warning: { border: '#f59e0b', icon: '#fcd34d' }
        };
        const c = colors[type] || colors.info;
        const toast = document.createElement('div');
        toast.className = 'toast pointer-events-auto rounded-xl px-4 py-3 flex items-center gap-3 min-w-64 max-w-sm';
        toast.style.cssText = `background:rgba(8,11,26,.95); border:1px solid ${c.border}; backdrop-filter:blur(20px); box-shadow:0 8px 32px rgba(0,0,0,.5);`;
        toast.innerHTML = `<i data-lucide="${icons[type]}" class="w-4 h-4 flex-shrink-0" style="color:${c.icon};"></i><span class="text-sm font-medium" style="color:rgba(255,255,255,.85);">${message}</span>`;
        document.getElementById('toastContainer').appendChild(toast);
        lucide.createIcons({ nodes: [toast] });
        const delay = type === 'warning' ? 7000 : 4000;
        setTimeout(() => {
            toast.classList.add('toast-out');
            setTimeout(() => toast.remove(), 280);
        }, delay);
    }

    function showError(message) {
        showToast(message, 'error');
        errorText.textContent = message;
        errorMessage.classList.remove('hidden');
        errorMessage.classList.add('flex');
    }

    // ── SHARED HELPERS ────────────────────────────────────────────────────
    function updateProcessBtn() {
        const icon = `<i data-lucide="play" class="w-4 h-4"></i>`;
        processBtn.innerHTML = selectedFiles.length > 0
            ? `${icon} Zpracovat (${selectedFiles.length} ${pluralFiles(selectedFiles.length)})`
            : `${icon} Zpracovat soubory`;
        lucide.createIcons({ nodes: [processBtn] });
    }

    function renderMonthsBadge(months) {
        if (months === null || months === undefined)
            return `<span style="color:rgba(255,255,255,.15);">—</span>`;
        if (months <= 0)
            return `<span class="text-xs font-bold" style="color:#f87171;">Vypršelo</span>`;
        if (months <= 3)
            return `<span class="text-xs font-bold" style="color:#fb923c;">${months} měs.</span>`;
        if (months <= 6)
            return `<span class="text-xs font-bold" style="color:#facc15;">${months} měs.</span>`;
        return `<span class="text-xs font-bold" style="color:#4ade80;">${months} měs.</span>`;
    }

    // ── FILE HANDLING ──────────────────────────────────────────────────────
    fileInput.addEventListener('change', e => handleFiles(e.target.files));

    uploadSection.addEventListener('dragover', e => {
        e.preventDefault();
        uploadSection.classList.add('drag-over');
    });
    uploadSection.addEventListener('dragleave', () => {
        uploadSection.classList.remove('drag-over');
    });
    uploadSection.addEventListener('drop', e => {
        e.preventDefault();
        uploadSection.classList.remove('drag-over');
        handleFiles(e.dataTransfer.files);
    });

    function pluralFiles(n) {
        if (n === 1) return 'soubor';
        if (n < 5)  return 'soubory';
        return 'souborů';
    }

    function handleFiles(files) {
        selectedFiles = Array.from(files).filter(f => f.name.endsWith('.csv'));
        updateFileList();
        processBtn.disabled = selectedFiles.length === 0;
        updateProcessBtn();
    }

    function extractCustomerFromFilename(filename) {
        let name = filename.replace(/\.csv$/i, '');
        name = name.replace(/_\d{8}$/, '');
        name = name.replace(/_\d{4}-\d{2}-\d{2}$/, '');
        name = name.replace(/[-_]/g, ' ').replace(/\s+/g, ' ').trim();
        return name;
    }

    function updateFileList() {
        if (selectedFiles.length === 0) { selectedFilesDiv.innerHTML = ''; return; }
        selectedFilesDiv.innerHTML = `<div class="text-xs font-semibold uppercase tracking-wide mb-2" style="color:var(--text-lo);">Vybrané soubory</div>`;
        selectedFiles.forEach((file, index) => {
            const suggested = extractCustomerFromFilename(file.name);
            const item = document.createElement('div');
            item.className = 'file-item';
            item.innerHTML = `
                <div class="flex items-center justify-between mb-2">
                    <div class="flex items-center gap-2 min-w-0">
                        <i data-lucide="file" class="w-3.5 h-3.5 flex-shrink-0" style="color:rgba(99,102,241,.6);"></i>
                        <span class="truncate text-xs" style="color:var(--text-md);">${file.name}</span>
                    </div>
                    <button onclick="removeFile(${index})" class="text-xs font-semibold flex-shrink-0 ml-2 transition-colors" style="color:rgba(248,113,113,.6);"
                            onmouseover="this.style.color='#f87171'" onmouseout="this.style.color='rgba(248,113,113,.6)'">Odebrat</button>
                </div>
                <div class="flex items-center gap-2">
                    <label class="text-xs whitespace-nowrap" style="color:var(--text-lo);">Přepsat zákazníka:</label>
                    <input type="text"
                        data-filename="${file.name}"
                        value="${suggested}"
                        placeholder="Ponechat prázdné → použít ze CSV"
                        class="glass-input text-xs py-1 min-w-0" style="font-size:12px; padding-top:5px; padding-bottom:5px;">
                </div>`;
            selectedFilesDiv.appendChild(item);
        });
        lucide.createIcons({ nodes: [selectedFilesDiv] });
    }

    function removeFile(index) {
        selectedFiles.splice(index, 1);
        updateFileList();
        processBtn.disabled = selectedFiles.length === 0;
        updateProcessBtn();
    }

    // ── UPLOAD ────────────────────────────────────────────────────────────
    processBtn.addEventListener('click', async () => {
        if (selectedFiles.length === 0) return;

        const customerNames = {};
        selectedFilesDiv.querySelectorAll('input[data-filename]').forEach(input => {
            const val = input.value.trim();
            const defaultVal = extractCustomerFromFilename(input.dataset.filename);
            if (val && val !== defaultVal) customerNames[input.dataset.filename] = val;
        });

        const formData = new FormData();
        selectedFiles.forEach(file => formData.append('files', file));
        formData.append('customer_names', JSON.stringify(customerNames));

        loadingDiv.classList.remove('hidden');
        loadingDiv.classList.add('flex');
        errorMessage.classList.add('hidden');
        errorMessage.classList.remove('flex');
        document.getElementById('loadingText').textContent = 'Zpracovávám soubory a načítám data smluv...';
        setLoading(processBtn, true);

        try {
            const response = await fetch('/upload', { method: 'POST', body: formData });
            const data = await response.json();
            if (data.error) { showError(data.error); return; }

            sessionId   = data.session_id;
            printerData = data.printer_list;
            serialMap   = Object.fromEntries(printerData.map(p => [p.serial, p]));
            displayPrinterSelection(printerData);
            setStep(2);
            showPanel('panel-select');
            showToast(`Zpracováno ${data.files_processed} souborů — nalezeno ${printerData.length} tiskáren`, 'success');

            if (data.warnings && data.warnings.length > 0) {
                data.warnings.forEach(w => showToast(w, 'warning'));
            }

            const dupWarning = document.getElementById('duplicateWarning');
            const dupList    = document.getElementById('duplicateList');
            if (data.duplicates && data.duplicates.length > 0) {
                dupList.innerHTML = data.duplicates.map(d =>
                    `<div class="flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg" style="background:rgba(245,158,11,.1); border:1px solid rgba(245,158,11,.2);">
                        <i data-lucide="copy" class="w-3 h-3 flex-shrink-0" style="color:#fbbf24;"></i>
                        <span class="font-mono font-semibold" style="color:#fde68a;">${d.serial}</span>
                        <span style="color:rgba(251,191,36,.7);">${d.model}</span>
                        <span style="color:rgba(251,191,36,.35);">—</span>
                        <span style="color:rgba(251,191,36,.8);">${d.sources.join(', ')}</span>
                    </div>`
                ).join('');
                dupWarning.classList.remove('hidden');
                lucide.createIcons({ nodes: [dupWarning] });
                showToast(`${data.duplicates.length} duplicitní sériová čísla — zkontrolujte upozornění`, 'warning');
            } else {
                dupWarning.classList.add('hidden');
            }

        } catch (error) {
            showError('Chyba při zpracování souborů: ' + error.message);
        } finally {
            loadingDiv.classList.add('hidden');
            loadingDiv.classList.remove('flex');
            setLoading(processBtn, false);
        }
    });

    // ── PRINTER SELECTION TABLE ────────────────────────────────────────────
    function displayPrinterSelection(printers) {
        const tbody = document.getElementById('printerTableBody');
        tbody.innerHTML = '';

        printers.forEach(printer => {
            const row = document.createElement('tr');
            row.dataset.customer   = printer.customer.toLowerCase();
            row.dataset.serial     = printer.serial.toLowerCase();
            row.dataset.status     = printer.status_color;
            row.dataset.hasContract = printer.has_contract ? '1' : '0';
            if (printer.is_duplicate) row.classList.add('row-dup');

            const dotClass = {
                green: 'dot dot-green', yellow: 'dot dot-yellow',
                orange: 'dot dot-orange', red: 'dot dot-red', gray: 'dot dot-gray'
            }[printer.status_color] || 'dot dot-gray';

            let badge = '';
            if (printer.contract_status === 'Active') {
                badge = printer.months_remaining !== null && printer.months_remaining <= 3
                    ? `<span class="cbadge cbadge-expiring">Vyprší brzy</span>`
                    : `<span class="cbadge cbadge-active">Aktivní</span>`;
            } else if (printer.months_remaining === 0) {
                badge = `<span class="cbadge cbadge-expired">Vypršelo</span>`;
            } else if (!printer.has_contract) {
                badge = `<span class="cbadge cbadge-none">Bez smlouvy</span>`;
            }

            const monthsBadge = renderMonthsBadge(printer.months_remaining);

            const cost = printer.monthly_cost > 0
                ? `<span class="font-bold" style="color:rgba(255,255,255,.9);">${printer.monthly_cost.toFixed(0)} Kč</span>`
                : `<span style="color:rgba(255,255,255,.15);">—</span>`;

            row.innerHTML = `
                <td class="px-3 py-2.5">
                    <input type="checkbox" class="printer-checkbox w-3.5 h-3.5 rounded" value="${printer.serial}" checked onchange="updateSelectionCount()">
                </td>
                <td class="px-2 py-2.5">
                    <span class="${dotClass}"></span>
                </td>
                <td class="px-3 py-2.5 font-semibold whitespace-nowrap" style="color:rgba(255,255,255,.85);">${printer.customer}</td>
                <td class="px-3 py-2.5 whitespace-nowrap" style="color:var(--text-md);">${printer.model}</td>
                <td class="px-3 py-2.5 font-mono text-xs ${printer.is_duplicate ? 'font-bold' : ''}" style="color:${printer.is_duplicate ? '#fbbf24' : 'rgba(255,255,255,.3)'};">
                    ${printer.serial}${printer.is_duplicate ? ' <span title="Tiskárna se vyskytuje ve více souborech">⚠</span>' : ''}
                </td>
                <td class="px-3 py-2.5">
                    <div class="flex flex-col gap-1">
                        <span class="text-xs font-medium" style="color:var(--text-md);">${printer.contract_name}</span>
                        ${badge}
                    </div>
                </td>
                <td class="col-extra hidden px-3 py-2.5 text-xs" style="color:var(--text-lo);">${printer.contract_type}</td>
                <td class="col-extra hidden px-3 py-2.5 text-xs" style="color:var(--text-lo);">${printer.end_date}</td>
                <td class="px-3 py-2.5">${monthsBadge}</td>
                <td class="px-3 py-2.5 text-right" style="color:var(--text-md);">${printer.bw_pages.toLocaleString('cs-CZ')}</td>
                <td class="px-3 py-2.5 text-right" style="color:var(--text-md);">${printer.color_pages.toLocaleString('cs-CZ')}</td>
                <td class="px-3 py-2.5 text-right">${cost}</td>
            `;
            tbody.appendChild(row);
        });

        updateSelectionCount();
        document.getElementById('selectAllCheckbox').checked = true;
        lucide.createIcons({ nodes: [tbody] });
    }

    // ── TABLE SEARCH + CONTRACT FILTER ────────────────────────────────────
    function filterTable() {
        const q = document.getElementById('printerSearch').value.toLowerCase().trim();
        document.querySelectorAll('#printerTableBody tr').forEach(row => {
            const textMatch = !q || (row.dataset.customer || '').includes(q) || (row.dataset.serial || '').includes(q);
            let contractMatch = true;
            if (contractFilter === 'expiring')   contractMatch = row.dataset.status === 'orange';
            else if (contractFilter === 'expired')    contractMatch = row.dataset.status === 'red';
            else if (contractFilter === 'nocontract') contractMatch = row.dataset.hasContract === '0';
            row.classList.toggle('hidden-row', !textMatch || !contractMatch);
        });
    }

    function setContractFilter(filter) {
        contractFilter = filter;
        document.querySelectorAll('.filter-chip').forEach(chip => {
            chip.classList.toggle('filter-chip-active', chip.dataset.filter === filter);
        });
        filterTable();
    }

    // ── COLUMN TOGGLE ──────────────────────────────────────────────────────
    function toggleExtraColumns() {
        extraColumnsVisible = !extraColumnsVisible;
        document.querySelectorAll('.col-extra').forEach(c => c.classList.toggle('hidden', !extraColumnsVisible));
        document.getElementById('colToggleBtn').textContent = extraColumnsVisible ? '− sloupce' : '+ sloupce';
    }

    // ── SELECTION HELPERS ──────────────────────────────────────────────────
    function toggleAll(checkbox) {
        document.querySelectorAll('.printer-table tbody .printer-checkbox').forEach(cb => cb.checked = checkbox.checked);
        updateSelectionCount();
    }

    function selectAll() {
        document.querySelectorAll('.printer-table tbody .printer-checkbox').forEach(cb => cb.checked = true);
        document.getElementById('selectAllCheckbox').checked = true;
        updateSelectionCount();
    }

    function deselectAll() {
        document.querySelectorAll('.printer-table tbody .printer-checkbox').forEach(cb => cb.checked = false);
        document.getElementById('selectAllCheckbox').checked = false;
        updateSelectionCount();
    }

    function selectWithContracts() {
        document.querySelectorAll('.printer-table tbody .printer-checkbox').forEach(cb => {
            const p = serialMap[cb.value];
            cb.checked = p ? p.has_contract : false;
        });
        updateSelectionCount();
    }

    function deselectDuplicates() {
        const dupeSerials = new Set(printerData.filter(p => p.is_duplicate).map(p => p.serial));
        document.querySelectorAll('.printer-table tbody .printer-checkbox').forEach(cb => {
            if (dupeSerials.has(cb.value)) cb.checked = false;
        });
        updateSelectionCount();
        showToast('Duplicitní tiskárny odebrány z výběru', 'warning');
    }

    function updateSelectionCount() {
        const checkedBoxes = document.querySelectorAll('.printer-table tbody .printer-checkbox:checked');
        const total = document.querySelectorAll('.printer-table tbody .printer-checkbox').length;
        let totalBW = 0, totalColor = 0;
        checkedBoxes.forEach(cb => {
            const p = serialMap[cb.value];
            if (p) { totalBW += p.bw_pages; totalColor += p.color_pages; }
        });
        document.getElementById('selectionCount').textContent = `${checkedBoxes.length} / ${total} vybráno`;
        document.getElementById('selectionStatsBW').textContent    = totalBW.toLocaleString('cs-CZ');
        document.getElementById('selectionStatsColor').textContent = totalColor.toLocaleString('cs-CZ');
    }

    // ── GENERATE REPORT ────────────────────────────────────────────────────
    async function generateReport() {
        const serials = Array.from(document.querySelectorAll('.printer-table tbody .printer-checkbox:checked')).map(cb => cb.value);
        if (serials.length === 0) { showToast('Vyberte alespoň jednu tiskárnu', 'error'); return; }

        const generateBtn = document.getElementById('generateBtn');
        setLoading(generateBtn, true);
        loadingDiv.classList.remove('hidden');
        loadingDiv.classList.add('flex');
        document.getElementById('loadingText').textContent = 'Generuji zprávu pro vybrané tiskárny...';
        showPanel('panel-upload');

        try {
            const response = await fetch('/generate_report', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: sessionId,
                    selected_printers: serials,
                    save_to_history: document.getElementById('save-to-history-checkbox')?.checked ?? false
                })
            });
            const data = await response.json();

            if (data.error) {
                showError(data.error);
                showPanel('panel-select');
                setStep(2);
                return;
            }

            displayResults(data.summary);
            setStep(4);
            showPanel('panel-results');
            showToast('Výkaz byl úspěšně vygenerován', 'success');

        } catch (error) {
            showError('Chyba při generování zprávy: ' + error.message);
            showPanel('panel-select');
            setStep(2);
        } finally {
            loadingDiv.classList.add('hidden');
            loadingDiv.classList.remove('flex');
            setLoading(generateBtn, false);
        }
    }

    // ── DISPLAY RESULTS ────────────────────────────────────────────────────
    function displayResults(summary) {
        document.getElementById('totalCustomers').textContent = summary.total_customers;
        document.getElementById('totalPrinters').textContent  = summary.total_printers;
        document.getElementById('totalBW').textContent        = summary.total_bw_all.toLocaleString('cs-CZ');
        document.getElementById('totalColor').textContent     = summary.total_color_all.toLocaleString('cs-CZ');

        const container = document.getElementById('customerDetailsContainer');
        container.innerHTML = '';

        summary.customer_details.forEach((customer, ci) => {
            const card = document.createElement('div');
            card.className = 'glass overflow-hidden';

            let printersHTML = '';
            customer.machines.forEach((machine, mi) => {
                const contract = machine.contract_info;
                let contractBlock = '';

                if (contract && contract.has_contract) {
                    const monthsText = contract.months_remaining != null ? `${contract.months_remaining} měsíců zbývá` : '—';
                    const costText   = contract.monthly_cost > 0 ? `${contract.monthly_cost.toFixed(2)} Kč/měs.` : '—';
                    contractBlock = `
                        <button class="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-md transition-all"
                                style="background:rgba(99,102,241,.1); color:#a5b4fc; border:1px solid rgba(99,102,241,.2);"
                                onmouseover="this.style.background='rgba(99,102,241,.18)'" onmouseout="this.style.background='rgba(99,102,241,.1)'"
                                onclick="toggleContract('c-${ci}-${mi}')">
                            <i data-lucide="clipboard-list" class="w-3 h-3"></i>
                            Detail smlouvy
                        </button>
                        <div id="c-${ci}-${mi}" class="hidden mt-2 text-xs rounded-xl p-3 grid grid-cols-2 gap-x-6 gap-y-2" style="background:rgba(255,255,255,.04); border:1px solid var(--glass-bdr);">
                            <div><span class="block mb-0.5" style="color:var(--text-lo);">Název smlouvy</span><span class="font-semibold" style="color:var(--text-hi);">${contract.contract_name}</span></div>
                            <div><span class="block mb-0.5" style="color:var(--text-lo);">Typ smlouvy</span><span class="font-semibold" style="color:var(--text-hi);">${contract.contract_type}</span></div>
                            <div><span class="block mb-0.5" style="color:var(--text-lo);">Stav</span><span class="font-semibold" style="color:var(--text-hi);">${contract.contract_status}</span></div>
                            <div><span class="block mb-0.5" style="color:var(--text-lo);">Zbývající čas</span><span class="font-bold" style="color:var(--text-hi);">${monthsText}</span></div>
                            <div><span class="block mb-0.5" style="color:var(--text-lo);">Datum začátku</span><span class="font-semibold" style="color:var(--text-hi);">${contract.start_date}</span></div>
                            <div><span class="block mb-0.5" style="color:var(--text-lo);">Datum ukončení</span><span class="font-semibold" style="color:var(--text-hi);">${contract.end_date}</span></div>
                            <div class="col-span-2 pt-2 mt-1" style="border-top:1px solid var(--glass-bdr);">
                                <span class="block mb-1" style="color:var(--text-lo);">Náklady</span>
                                <div class="flex gap-4" style="color:var(--text-md);">
                                    <span>Pevné: <strong style="color:var(--text-hi);">${contract.fixed_cost.toFixed(2)} Kč</strong></span>
                                    <span>Stránky: <strong style="color:var(--text-hi);">${contract.page_cost.toFixed(2)} Kč</strong></span>
                                    <span class="font-bold" style="color:#4ade80;">Celkem: ${costText}</span>
                                </div>
                            </div>
                        </div>`;
                } else {
                    contractBlock = `
                        <div class="mt-2 text-xs inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md" style="background:rgba(245,158,11,.1); border:1px solid rgba(245,158,11,.2); color:rgba(251,191,36,.8);">
                            <i data-lucide="alert-triangle" class="w-3 h-3"></i>
                            Bez smlouvy
                        </div>`;
                }

                printersHTML += `
                    <div class="flex items-start justify-between py-3" style="border-bottom:1px solid rgba(255,255,255,.04);">
                        <div class="flex-1">
                            <div class="flex items-center gap-2">
                                <span class="text-sm font-bold" style="color:var(--text-hi);">${machine.model}</span>
                                <span class="font-mono text-xs" style="color:var(--text-lo);">${machine.serial}</span>
                            </div>
                            ${contractBlock}
                        </div>
                        <div class="flex items-center gap-5 text-xs ml-4 mt-0.5 flex-shrink-0" style="color:var(--text-lo);">
                            <div class="text-right">
                                <div class="font-bold text-sm" style="color:var(--text-hi);">${machine.bw_billable.toLocaleString('cs-CZ')}</div>
                                <div>ČB</div>
                            </div>
                            <div class="text-right">
                                <div class="font-bold text-sm" style="color:var(--text-hi);">${machine.color_billable.toLocaleString('cs-CZ')}</div>
                                <div>Barva</div>
                            </div>
                        </div>
                    </div>`;
            });

            card.innerHTML = `
                <div class="px-5 py-4 flex items-center justify-between flex-wrap gap-3" style="background:rgba(255,255,255,.03); border-bottom:1px solid var(--glass-bdr);">
                    <div class="flex items-center gap-2.5">
                        <i data-lucide="building-2" class="w-4 h-4" style="color:rgba(99,102,241,.6);"></i>
                        <span class="font-bold text-white">${customer.customer}</span>
                        <span class="text-xs px-2 py-0.5 rounded-full" style="background:rgba(255,255,255,.06); color:var(--text-lo); border:1px solid var(--glass-bdr);">${customer.printers} tiskáren</span>
                    </div>
                    <div class="flex items-center gap-4 text-xs" style="color:var(--text-lo);">
                        <span><strong style="color:var(--text-hi);">${customer.total_bw_billable.toLocaleString('cs-CZ')}</strong> ČB</span>
                        <span><strong style="color:var(--text-hi);">${customer.total_color_billable.toLocaleString('cs-CZ')}</strong> barva</span>
                        <span style="color:rgba(255,255,255,.15);">${customer.date_range}</span>
                    </div>
                </div>
                <div class="px-5">${printersHTML}</div>`;

            container.appendChild(card);
        });

        document.getElementById('downloadPDF').href     = `/download/${sessionId}/pdf`;
        document.getElementById('downloadDetails').href = `/download/${sessionId}/details`;
        document.getElementById('downloadInvoice').href = `/download/${sessionId}/invoice`;
        document.getElementById('downloadAll').href     = `/download_all/${sessionId}`;

        lucide.createIcons();
    }

    // ── TOGGLE CONTRACT ────────────────────────────────────────────────────
    function toggleContract(id) {
        const el = document.getElementById(id);
        el.classList.toggle('hidden');
        lucide.createIcons({ nodes: [el.parentElement] });
    }

    // ── CONTRACT MANAGEMENT ────────────────────────────────────────────────
    let contractsData = [];
    let editingSerial = null;

    function showContractsPanel() {
        PANELS.forEach(p => {
            const el = document.getElementById(p);
            el.classList.toggle('hidden', p !== 'panel-contracts');
            if (p === 'panel-contracts') {
                el.classList.add('panel-enter');
                setTimeout(() => el.classList.remove('panel-enter'), 400);
            }
        });
        document.getElementById('topBarTitle').textContent = 'Správa smluv';
        document.getElementById('stepBadge').textContent = 'Smlouvy';
        for (let i = 1; i <= 4; i++) {
            const btn = document.getElementById('nav-' + i);
            if (btn) btn.classList.remove('step-active');
        }
        const navBtn = document.getElementById('nav-contracts');
        navBtn.style.background = 'rgba(99,102,241,.12)';
        navBtn.querySelector('.sb-label').style.color = '#fff';
        loadContracts();
        lucide.createIcons();
    }

    async function loadContracts() {
        try {
            const res = await fetch('/contracts/list');
            const data = await res.json();
            contractsData = data.contracts || [];
            renderContractsTable(contractsData);
            updateContractStats(contractsData);
            lucide.createIcons();
        } catch (e) {
            showToast('Chyba při načítání smluv', 'error');
        }
    }

    function updateContractStats(contracts) {
        document.getElementById('ct-total').textContent    = contracts.length;
        document.getElementById('ct-active').textContent   = contracts.filter(c => c.status_color === 'green' || c.status_color === 'yellow').length;
        document.getElementById('ct-expiring').textContent = contracts.filter(c => c.status_color === 'orange').length;
        document.getElementById('ct-expired').textContent  = contracts.filter(c => c.status_color === 'red').length;
    }

    function renderContractsTable(contracts) {
        const tbody = document.getElementById('contractsTableBody');
        const empty = document.getElementById('contractsEmpty');
        tbody.innerHTML = '';
        if (contracts.length === 0) { empty.classList.remove('hidden'); return; }
        empty.classList.add('hidden');
        contracts.forEach(c => {
            const dotClass = { green:'dot dot-green', yellow:'dot dot-yellow', orange:'dot dot-orange', red:'dot dot-red', gray:'dot dot-gray' }[c.status_color] || 'dot dot-gray';
            const monthsText = renderMonthsBadge(c.months_remaining);
            const serialEsc = c.serial.replace(/'/g, "\\'");
            const row = document.createElement('tr');
            row.dataset.serial   = c.serial.toLowerCase();
            row.dataset.customer = c.customer_location.toLowerCase();
            row.innerHTML = `
                <td class="px-3 py-2.5 font-mono text-xs" style="color:rgba(255,255,255,.4);">${c.serial}</td>
                <td class="px-3 py-2.5 font-semibold text-xs" style="color:var(--text-hi);">${c.contract_name}</td>
                <td class="px-3 py-2.5 text-xs" style="color:var(--text-md);">${c.customer_location}</td>
                <td class="px-3 py-2.5 text-xs" style="color:var(--text-lo);">${c.contract_type}</td>
                <td class="px-3 py-2.5 text-xs" style="color:var(--text-lo);">${c.end_date}</td>
                <td class="px-3 py-2.5 text-xs">${monthsText}</td>
                <td class="px-3 py-2.5 text-right text-xs" style="color:var(--text-md);">${c.monthly_fixed_cost.toFixed(0)} Kč</td>
                <td class="px-3 py-2.5 text-right text-xs" style="color:var(--text-md);">${c.bw_cost_per_page.toFixed(4)}</td>
                <td class="px-3 py-2.5 text-right text-xs" style="color:var(--text-md);">${c.color_cost_per_page.toFixed(4)}</td>
                <td class="px-3 py-2.5"><span class="${dotClass}"></span></td>
                <td class="px-3 py-2.5 text-center">
                    <div class="flex justify-center gap-1.5">
                        <button onclick="openContractModal('${serialEsc}')" class="btn btn-ghost btn-sm" style="padding:3px 8px; font-size:11px;">
                            <i data-lucide="pencil" class="w-3 h-3"></i>
                        </button>
                        <button onclick="confirmDeleteContract(this,'${serialEsc}')" class="btn btn-sm" style="padding:3px 8px; font-size:11px; background:rgba(239,68,68,.1); color:#f87171; border:1px solid rgba(239,68,68,.2);"
                                onmouseover="this.style.background='rgba(239,68,68,.2)'" onmouseout="this.style.background='rgba(239,68,68,.1)'">
                            <i data-lucide="trash-2" class="w-3 h-3"></i>
                        </button>
                    </div>
                </td>`;
            tbody.appendChild(row);
        });
    }

    function filterContracts() {
        const q = document.getElementById('contractSearch').value.toLowerCase().trim();
        document.querySelectorAll('#contractsTableBody tr').forEach(row => {
            const match = !q || (row.dataset.serial || '').includes(q) || (row.dataset.customer || '').includes(q);
            row.classList.toggle('hidden', !match);
        });
    }

    function openContractModal(serial = null) {
        editingSerial = serial;
        document.getElementById('contractModalTitle').textContent = serial ? 'Upravit smlouvu' : 'Přidat smlouvu';
        document.getElementById('cf-original-serial').value = serial || '';
        if (serial) {
            const c = contractsData.find(x => x.serial === serial);
            if (!c) return;
            document.getElementById('cf-serial').value   = c.serial;
            document.getElementById('cf-name').value     = c.contract_name;
            document.getElementById('cf-location').value = c.customer_location;
            document.getElementById('cf-type').value     = c.contract_type;
            document.getElementById('cf-start').value    = c.start_date;
            document.getElementById('cf-end').value      = c.end_date;
            document.getElementById('cf-fixed').value    = c.monthly_fixed_cost;
            document.getElementById('cf-bw').value       = c.bw_cost_per_page;
            document.getElementById('cf-color').value    = c.color_cost_per_page;
            document.getElementById('cf-min-vol').value  = c.minimum_monthly_volume;
            document.getElementById('cf-status').value   = c.status;
            document.getElementById('cf-notes').value    = c.notes;
        } else {
            document.getElementById('contractForm').reset();
        }
        document.getElementById('contractModal').classList.remove('hidden');
        lucide.createIcons();
    }

    function closeContractModal() {
        document.getElementById('contractModal').classList.add('hidden');
        editingSerial = null;
    }

    async function saveContract() {
        const serial = document.getElementById('cf-serial').value.trim();
        if (!serial) { showToast('Sériové číslo je povinné', 'error'); return; }
        const btn = document.getElementById('saveContractBtn');
        setLoading(btn, true);
        const payload = {
            serial,
            contract_name:          document.getElementById('cf-name').value.trim(),
            customer_location:      document.getElementById('cf-location').value.trim(),
            contract_type:          document.getElementById('cf-type').value.trim(),
            start_date:             document.getElementById('cf-start').value.trim(),
            end_date:               document.getElementById('cf-end').value.trim(),
            monthly_fixed_cost:     document.getElementById('cf-fixed').value,
            bw_cost_per_page:       document.getElementById('cf-bw').value,
            color_cost_per_page:    document.getElementById('cf-color').value,
            minimum_monthly_volume: document.getElementById('cf-min-vol').value,
            status:                 document.getElementById('cf-status').value,
            notes:                  document.getElementById('cf-notes').value.trim(),
        };
        const url = editingSerial ? `/contracts/edit/${encodeURIComponent(editingSerial)}` : '/contracts/add';
        try {
            const res  = await fetch(url, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
            const data = await res.json();
            if (data.error) { showToast(data.error, 'error'); return; }
            showToast(editingSerial ? 'Smlouva aktualizována' : 'Smlouva přidána', 'success');
            closeContractModal();
            loadContracts();
        } catch (e) {
            showToast('Chyba při ukládání', 'error');
        } finally {
            setLoading(btn, false);
        }
    }

    async function confirmDeleteContract(btn, serial) {
        if (!confirm(`Opravdu smazat smlouvu pro sériové číslo ${serial}?`)) return;
        setLoading(btn, true);
        try {
            const res  = await fetch(`/contracts/delete/${encodeURIComponent(serial)}`, { method: 'POST' });
            const data = await res.json();
            if (data.error) { showToast(data.error, 'error'); return; }
            showToast('Smlouva smazána', 'warning');
            loadContracts();
        } catch (e) {
            showToast('Chyba při mazání', 'error');
        } finally {
            setLoading(btn, false);
        }
    }

    async function reloadContracts() {
        const btn = document.getElementById('reloadBtn');
        setLoading(btn, true);
        try {
            const res  = await fetch('/contracts/reload', { method: 'POST' });
            const data = await res.json();
            showToast(`Znovu načteno: ${data.count} smluv`, 'success');
            loadContracts();
        } catch (e) {
            showToast('Chyba při načítání', 'error');
        } finally {
            setLoading(btn, false);
        }
    }
