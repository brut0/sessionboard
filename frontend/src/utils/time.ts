export const WORK_START_MINUTES = 480; // 08:00
export const WORK_END_MINUTES = 1200; // 20:00
export const TOTAL_WORK_MINUTES = WORK_END_MINUTES - WORK_START_MINUTES; // 720 min

export interface WeekDayInfo {
  date: string;
  shortName: string;
  fullName: string;
  dayNumber: string;
  monthShort: string;
}

const WEEKDAY_SHORT = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const WEEKDAY_FULL = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
];
const MONTH_SHORT = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
];

/** Convert "HH:MM" into integer minutes since midnight. */
export function timeToMinutes(hhmm: string): number {
  const [hStr, mStr] = hhmm.split(':');
  const h = Number(hStr);
  const m = Number(mStr);
  if (Number.isNaN(h) || Number.isNaN(m)) return 0;
  return h * 60 + m;
}

/** Convert integer minutes since midnight into "HH:MM". */
export function minutesToTime(minutes: number): string {
  const clamped = Math.max(0, Math.min(1439, Math.round(minutes)));
  const h = Math.floor(clamped / 60);
  const m = clamped % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

/** Shift a YYYY-MM-DD date string by deltaDays using UTC-safe arithmetic. */
export function shiftDate(dateStr: string, deltaDays: number): string {
  const parts = dateStr.split('-').map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) {
    return dateStr;
  }
  const [y, m, d] = parts;
  return new Date(Date.UTC(y, m - 1, d + deltaDays)).toISOString().split('T')[0];
}

/** Return today's local date as YYYY-MM-DD. */
export function getTodayIso(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

/** Format YYYY-MM-DD into a concise readable label such as "Fri, Nov 20, 2026". */
export function formatReadableDate(dateStr: string): string {
  const parts = dateStr.split('-').map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) {
    return dateStr;
  }
  const [y, m, d] = parts;
  const dt = new Date(Date.UTC(y, m - 1, d));
  const isoDow = dt.getUTCDay() === 0 ? 6 : dt.getUTCDay() - 1;
  return `${WEEKDAY_SHORT[isoDow]}, ${MONTH_SHORT[dt.getUTCMonth()]} ${dt.getUTCDate()}, ${dt.getUTCFullYear()}`;
}

/** Return Monday..Sunday metadata for the ISO week containing dateStr. */
export function getWeekDays(dateStr: string): WeekDayInfo[] {
  const parts = dateStr.split('-').map(Number);
  const baseDateStr =
    parts.length === 3 && !parts.some(Number.isNaN) ? dateStr : getTodayIso();
  const [y, m, d] = baseDateStr.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  const utcDay = dt.getUTCDay(); // 0 = Sun, 1 = Mon, ...
  const diffToMonday = utcDay === 0 ? -6 : 1 - utcDay;

  const days: WeekDayInfo[] = [];
  for (let i = 0; i < 7; i++) {
    const isoDate = shiftDate(baseDateStr, diffToMonday + i);
    const [iy, im, id] = isoDate.split('-').map(Number);
    const dayDt = new Date(Date.UTC(iy, im - 1, id));
    days.push({
      date: isoDate,
      shortName: WEEKDAY_SHORT[i],
      fullName: WEEKDAY_FULL[i],
      dayNumber: String(id),
      monthShort: MONTH_SHORT[dayDt.getUTCMonth()],
    });
  }
  return days;
}
