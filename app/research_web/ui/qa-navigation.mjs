const QA = 'alphadesk';

export const qaEnabled = runtime => runtime?.execution_engine === QA;
export const isQASession = session => session?.mode === 'fingpt' && session.execution_engine === QA;
export const isSpecialistSession = session => session?.mode === 'fingpt' && session.research_mode === 'specialist' && !isQASession(session);

export function researchSessionPage(session) {
  if (session.mode === 'claw') return 'claw';
  if (isQASession(session)) return 'qa';
  if (isSpecialistSession(session)) return 'specialist';
  return 'fingpt';
}

export function visibleResearchSessions(sessions, enabled) {
  return enabled ? sessions.filter(session => session.mode !== 'fingpt' || isQASession(session) || isSpecialistSession(session)) : sessions;
}

export function fingptReplacement(session, sessionId = '') {
  if (isQASession(session) || isSpecialistSession(session)) {
    return `#/${researchSessionPage(session)}?session=${encodeURIComponent(sessionId)}`;
  }
  return '#/qa';
}
