/** Display helpers for saved Nudge calls. Formatted by hand rather than
 * via toLocaleString so the output is identical on Hermes (Android/iOS)
 * and in the browser. */

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const SURFACE_LABEL: Record<string, string> = {
  home: 'Home',
  progress: 'Progress',
  insights: 'Insights',
  'risk-profile': 'Risk profile',
  allocation: 'Allocation',
};

/** "24 Oct 2026, 3:42 pm" */
export function formatCallTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const hours = d.getHours();
  const minutes = String(d.getMinutes()).padStart(2, '0');
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}, ${hours % 12 || 12}:${minutes} ${hours < 12 ? 'am' : 'pm'}`;
}

/** "4 min", "under a minute", or null while a call has no end time. */
export function formatCallDuration(startedAt: string, endedAt: string | null): string | null {
  if (!endedAt) return null;
  const ms = new Date(endedAt).getTime() - new Date(startedAt).getTime();
  if (!Number.isFinite(ms) || ms < 0) return null;
  const minutes = Math.round(ms / 60_000);
  return minutes < 1 ? 'under a minute' : `${minutes} min`;
}

export function surfaceLabel(surface: string): string {
  return SURFACE_LABEL[surface] ?? surface;
}
