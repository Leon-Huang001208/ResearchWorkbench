import { escapeHTML as e } from './markdown.mjs';
import { icon } from './icons.mjs';
import { isRunning, safeLog } from './core.mjs';

const coordinate = value => Number.isFinite(value) ? Math.max(0, value) : 8;
const placement = position => `--menu-left:${coordinate(position?.left)}px;--menu-top:${coordinate(position?.top)}px`;
const separator = '<div class="conversation-menu-separator" role="separator"></div>';
const item = (attrs, glyph, text, disabled = false, extra = '') => `<button type="button" role="menuitem" ${attrs} ${disabled ? 'disabled' : ''} ${extra}>${icon(glyph)}<span class="conversation-menu-label">${e(text)}</span></button>`;

/** Fixed viewport coordinates; callers pass the actual parent menu bounds. */
export function projectMenuPosition(rect, { width, height }) {
  const viewportWidth = Number.isFinite(width) ? Math.max(0, width) : 320;
  const viewportHeight = Number.isFinite(height) ? Math.max(0, height) : 640;
  const menuWidth = Math.min(232, Math.max(0, viewportWidth - 16));
  const left = coordinate(rect?.left);
  const right = Number.isFinite(rect?.right) ? rect.right : left + 208;
  const maxLeft = Math.max(8, viewportWidth - menuWidth - 8);
  const desired = viewportWidth <= 640 ? left : right + 4 + menuWidth <= viewportWidth - 8 ? right + 4 : left - menuWidth - 4;
  return {
    left: Math.min(maxLeft, Math.max(8, desired)),
    top: Math.min(Math.max(8, viewportHeight - 300 - 8), Math.max(8, coordinate(rect?.top))),
    width: menuWidth,
  };
}

/** Keep the source row unobscured; narrow panes fall back below that row. */
export function sessionMenuPosition(rect, { width, height }) {
  const viewportWidth = Number.isFinite(width) ? width : 320;
  const viewportHeight = Number.isFinite(height) ? height : 640;
  const menuWidth = Math.min(208, Math.max(0, viewportWidth - 16));
  const menuHeight = Math.min(280, Math.max(0, viewportHeight - 16));
  const right = Number.isFinite(rect?.right) ? rect.right : 68;
  const left = Number.isFinite(rect?.left) ? rect.left : right;
  let x, y = Number.isFinite(rect?.top) ? rect.top : 8;
  if (right + 6 + menuWidth <= viewportWidth - 8) x = right + 6;
  else if (left - 6 - menuWidth >= 8) x = left - 6 - menuWidth;
  else {
    x = Math.max(8, Math.min(viewportWidth - menuWidth - 8, right - menuWidth));
    const bottom = Number.isFinite(rect?.bottom) ? rect.bottom : y + 32;
    y = bottom + 6 + menuHeight <= viewportHeight - 8 ? bottom + 6 : y - menuHeight - 6;
  }
  return { left: Math.max(8, Math.min(viewportWidth - menuWidth - 8, x)), top: Math.max(8, Math.min(viewportHeight - menuHeight - 8, y)), width: menuWidth };
}

function orderItems(kind, id, group, disabled) {
  const attrs = `data-nav-group="${e(group)}" data-nav-entity="${kind}" data-nav-id="${e(id)}"`;
  return item(`data-nav-order="-1" ${attrs}`, 'arrowUp', '上移', disabled)
    + item(`data-nav-order="1" ${attrs}`, 'arrowDown', '下移', disabled);
}

function projectChoices(session, navigation, move) {
  if (!move) return '';
  const projects = (navigation?.projects || []).filter(project => !project.archived);
  const current = session.project_id || 'default';
  return `<div class="session-project-menu conversation-action-menu" role="menu" aria-label="选择项目" style="${placement(move)};--project-menu-width:${Math.min(232, coordinate(move.width ?? 232))}px"><div class="session-project-menu-list">${projects.length ? projects.map(project => `<button type="button" role="menuitemradio" aria-checked="${project.id === current}" data-nav-move-target="${e(project.id)}" data-nav-session="${e(session.id)}" title="${e(project.name)}" ${navigation.busy ? 'disabled' : ''}>${icon('folder')}<span class="conversation-menu-label">${e(project.name)}</span>${project.id === current ? icon('check') : ''}</button>`).join('') : '<p class="conversation-menu-empty" role="status">暂无可用项目</p>'}</div></div>`;
}

export function renderSessionMenu({ session, position, navigation, move = null }) {
  if (!session?.id) { safeLog('navigation_menu_session_missing'); return ''; }
  const id = e(session.id);
  const running = isRunning(session.status);
  const pinned = Boolean(navigation?.metadata?.pinned?.some(entity => entity.kind === 'session' && entity.id === session.id));
  const disabled = Boolean(navigation?.busy || !navigation?.loaded);
  const choices = navigation ? separator
    + item(`data-nav-pin="session" data-nav-id="${id}"`, 'pin', pinned ? '取消置顶' : '置顶', disabled)
    + (pinned ? orderItems('session', session.id, 'pinned', disabled) : '')
    + item(`data-nav-move-menu="${id}" aria-haspopup="menu" aria-expanded="${Boolean(move)}"`, 'folder', '移动到项目', disabled, 'class="conversation-menu-move"').replace('</button>', `${icon('chevronRight')}</button>`) : '';
  return `<div class="session-action-menu conversation-action-menu" role="menu" aria-label="会话操作" style="${placement(position)}"><div class="session-menu-items">${item(`data-menu-rename="${id}"`, 'rename', '重命名')}${choices}${separator}${item(`data-menu-delete="${id}"`, 'trash', '删除', running, `class="danger-item" ${running ? 'aria-describedby="session-delete-reason"' : ''}`)}${running ? '<p id="session-delete-reason" class="menu-reason">任务运行或等待处理时不能删除</p>' : ''}</div>${projectChoices(session, navigation, move)}</div>`;
}

export function renderProjectActionsMenu({ project, position, pinned = false, group = 'project', busy = false, mode = 'claw' }) {
  if (!project?.id) { safeLog('navigation_menu_project_missing'); return ''; }
  const id = e(project.id);
  return `<div class="nav-project-menu conversation-action-menu" role="menu" aria-label="项目操作" style="${placement(position)}"><div class="session-menu-items">${item(`data-nav-pin="project" data-nav-id="${id}"`, 'pin', pinned ? '取消置顶' : '置顶', busy)}${orderItems('project', project.id, group, busy)}${separator}${project.id !== 'default' ? item(`data-nav-project-rename="${id}"`, 'rename', '重命名', busy) : ''}${item(`data-nav-new-in-project="${id}"`, 'compose', '在项目中新聊天', busy)}<a role="menuitem" href="#/${mode === 'fingpt' ? 'fingpt' : 'claw'}?view=projects&project=${encodeURIComponent(project.id)}">${icon('document')}<span class="conversation-menu-label">项目资料与产物</span></a>${project.id !== 'default' ? separator + item(`data-nav-project-archive="${id}"`, 'archive', '归档项目', busy) : ''}</div></div>`;
}
