/* ============================================================
   AlphaFoundry — Navigation Curation
   Keeps the current WebUI focused without deleting in-development pages.
   ============================================================ */

const ARCHIVED_SECTIONS = [
    'scenario',
    'industry-chain',
    'review',
    'outcomes',
    'ingest',
];

const STORAGE_KEY = 'af-show-archived-sections';

function isArchivedSection(section) {
    return ARCHIVED_SECTIONS.includes(section);
}

function archivedSectionsVisible() {
    return localStorage.getItem(STORAGE_KEY) === 'true';
}

function setArchivedSectionsVisible(visible) {
    localStorage.setItem(STORAGE_KEY, visible ? 'true' : 'false');
    applyArchivedVisibility(visible);
}

function applyArchivedVisibility(visible = archivedSectionsVisible()) {
    document.body.classList.toggle('show-archived-sections', visible);
    document.querySelectorAll('.activity-btn[data-section]').forEach(btn => {
        const archived = isArchivedSection(btn.dataset.section);
        btn.classList.toggle('activity-btn-archived', archived);
        btn.classList.toggle('activity-btn-hidden', archived && !visible);
    });

    const toggle = document.getElementById('btn-toggle-archived-sections');
    if (toggle) {
        toggle.classList.toggle('active', visible);
        toggle.title = visible ? '隐藏待开发入口' : '显示待开发入口';
        toggle.setAttribute('aria-label', visible ? '隐藏待开发入口' : '显示待开发入口');
        toggle.setAttribute('aria-pressed', visible ? 'true' : 'false');
    }
}

function ensureArchivedToggle() {
    const barTop = document.querySelector('.activity-bar-top');
    if (!barTop || document.getElementById('btn-toggle-archived-sections')) return;

    const btn = document.createElement('button');
    btn.className = 'activity-btn activity-btn-more';
    btn.id = 'btn-toggle-archived-sections';
    btn.type = 'button';
    btn.title = '显示待开发入口';
    btn.setAttribute('aria-label', '显示待开发入口');
    btn.setAttribute('aria-pressed', 'false');
    btn.innerHTML = '<i class="codicon codicon-ellipsis"></i>';
    btn.addEventListener('click', () => {
        setArchivedSectionsVisible(!archivedSectionsVisible());
    });

    const firstArchivedBtn = barTop.querySelector(`.activity-btn[data-section="${ARCHIVED_SECTIONS[0]}"]`);
    if (firstArchivedBtn) {
        barTop.insertBefore(btn, firstArchivedBtn);
    } else {
        barTop.appendChild(btn);
    }
}

function initNavigationCuration() {
    ensureArchivedToggle();
    applyArchivedVisibility();
}

export {
    ARCHIVED_SECTIONS,
    initNavigationCuration,
    isArchivedSection,
    setArchivedSectionsVisible,
};
