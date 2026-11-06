// Brasília is UTC−03:00. The collection is scheduled for Monday at 07:00.
export function hasCurrentWeeklyCollection(completedAt: string, now = Date.now()) {
  const completed = Date.parse(completedAt);
  if (!Number.isFinite(completed) || completed > now) return false;
  const local = new Date(now - 3 * 3600000);
  const sinceMonday = (local.getUTCDay() + 6) % 7;
  let latestScheduled = Date.UTC(local.getUTCFullYear(), local.getUTCMonth(), local.getUTCDate() - sinceMonday, 10);
  if (now < latestScheduled) latestScheduled -= 7 * 86400000;
  return completed >= latestScheduled;
}
