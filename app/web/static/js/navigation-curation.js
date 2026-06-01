/* ============================================================
   AlphaFoundry — Navigation Curation
   Keeps the current WebUI focused without deleting legacy pages.
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
        toggle.title = visible ? '隐藏归档页面' : '显示归档页面';
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
    btn.title = '显示归档页面';
    btn.setAttribute('aria-label', '显示归档页面');
    btn.setAttribute('aria-pressed', 'false');
    btn.innerHTML = '<i class="codicon codicon-ellipsis"></i>';
    btn.addEventListener('click', () => {
        setArchivedSectionsVisible(!archivedSectionsVisible());
    });

    const templatesBtn = barTop.querySelector('.activity-btn[data-section="templates"]');
    if (templatesBtn) {
        barTop.insertBefore(btn, templatesBtn);
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
