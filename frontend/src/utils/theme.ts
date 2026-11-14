export interface SpecialtyTheme {
  name: string;
  accentColor: string;
  bgBadge: string;
  textBadge: string;
  borderBadge: string;
  ganttBg: string;
  ganttBorder: string;
  avatarBg: string;
  avatarText: string;
}

const STUDIO_PALETTE: SpecialtyTheme[] = [
  {
    name: 'indigo',
    accentColor: '#4f46e5',
    bgBadge: 'bg-indigo-50',
    textBadge: 'text-indigo-700',
    borderBadge: 'border-indigo-200',
    ganttBg: 'bg-indigo-50/90',
    ganttBorder: 'border-indigo-300',
    avatarBg: 'bg-indigo-100',
    avatarText: 'text-indigo-700',
  },
  {
    name: 'emerald',
    accentColor: '#059669',
    bgBadge: 'bg-emerald-50',
    textBadge: 'text-emerald-700',
    borderBadge: 'border-emerald-200',
    ganttBg: 'bg-emerald-50/90',
    ganttBorder: 'border-emerald-300',
    avatarBg: 'bg-emerald-100',
    avatarText: 'text-emerald-700',
  },
  {
    name: 'amber',
    accentColor: '#d97706',
    bgBadge: 'bg-amber-50',
    textBadge: 'text-amber-800',
    borderBadge: 'border-amber-200',
    ganttBg: 'bg-amber-50/90',
    ganttBorder: 'border-amber-300',
    avatarBg: 'bg-amber-100',
    avatarText: 'text-amber-800',
  },
  {
    name: 'sky',
    accentColor: '#0284c7',
    bgBadge: 'bg-sky-50',
    textBadge: 'text-sky-700',
    borderBadge: 'border-sky-200',
    ganttBg: 'bg-sky-50/90',
    ganttBorder: 'border-sky-300',
    avatarBg: 'bg-sky-100',
    avatarText: 'text-sky-700',
  },
  {
    name: 'violet',
    accentColor: '#7c3aed',
    bgBadge: 'bg-violet-50',
    textBadge: 'text-violet-700',
    borderBadge: 'border-violet-200',
    ganttBg: 'bg-violet-50/90',
    ganttBorder: 'border-violet-300',
    avatarBg: 'bg-violet-100',
    avatarText: 'text-violet-700',
  },
  {
    name: 'rose',
    accentColor: '#e11d48',
    bgBadge: 'bg-rose-50',
    textBadge: 'text-rose-700',
    borderBadge: 'border-rose-200',
    ganttBg: 'bg-rose-50/90',
    ganttBorder: 'border-rose-300',
    avatarBg: 'bg-rose-100',
    avatarText: 'text-rose-700',
  },
];

function hashSeed(seed: string | number): number {
  if (typeof seed === 'number' && Number.isFinite(seed)) {
    return Math.abs(Math.trunc(seed));
  }
  const str = String(seed || 'studio');
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash * 31 + str.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

/** Deterministically map a specialist name, specialty, or ID to a studio color theme. */
export function getSpecialtyTheme(seed: string | number): SpecialtyTheme {
  const idx = hashSeed(seed) % STUDIO_PALETTE.length;
  return STUDIO_PALETTE[idx];
}

/** Extract 1-2 uppercase initials from a person's display name. */
export function getInitials(name: string): string {
  const parts = (name || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (parts.length === 0) return 'S';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}
