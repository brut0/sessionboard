import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  Calendar,
  Plus,
  Clock,
  User,
  CheckCircle2,
  XCircle,
  AlertCircle,
  LayoutGrid,
  GanttChart,
  Printer,
  RotateCw,
  DoorOpen,
  X,
  CalendarPlus,
  Filter,
  Activity,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { apiClient, type Room, type Session, type Specialist } from '../api/client';
import {
  WORK_START_MINUTES,
  WORK_END_MINUTES,
  TOTAL_WORK_MINUTES,
  timeToMinutes,
  shiftDate,
  getTodayIso,
  formatReadableDate,
} from '../utils/time';
import { getSpecialtyTheme, getInitials } from '../utils/theme';

export interface BookingPrefill {
  roomId?: number;
  specialistId?: number;
  clientId?: number;
  startTime?: string;
  date?: string;
}

interface DayBoardProps {
  selectedDate: string;
  onDateChange: (date: string) => void;
  onOpenBookingModal: (prefill?: BookingPrefill) => void;
  refreshTrigger?: number;
}

type ViewMode = 'columns' | 'gantt';
type GanttGroupBy = 'room' | 'specialist';
type StatusFilter = 'all' | 'planned' | 'done' | 'cancelled';

const GANTT_HOURS = Array.from({ length: 12 }, (_, idx) => {
  const hour = 8 + idx;
  return `${String(hour).padStart(2, '0')}:00`;
});

export const DayBoard: React.FC<DayBoardProps> = ({
  selectedDate,
  onDateChange,
  onOpenBookingModal,
  refreshTrigger = 0,
}) => {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [specialists, setSpecialists] = useState<Specialist[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const [viewMode, setViewMode] = useState<ViewMode>('columns');
  const [ganttGroupBy, setGanttGroupBy] = useState<GanttGroupBy>('room');
  const [selectedSpecialistId, setSelectedSpecialistId] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [drawerSessionId, setDrawerSessionId] = useState<number | null>(null);
  const [nowClock, setNowClock] = useState<{ label: string; minutes: number }>({
    label: '',
    minutes: 0,
  });

  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      const hh = String(now.getHours()).padStart(2, '0');
      const mm = String(now.getMinutes()).padStart(2, '0');
      setNowClock({
        label: `${hh}:${mm}`,
        minutes: now.getHours() * 60 + now.getMinutes(),
      });
    };
    updateClock();
    const timer = setInterval(updateClock, 30000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    setSelectedSpecialistId(null);
    setDrawerSessionId(null);
  }, [selectedDate]);

  const fetchBoardData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [roomsRes, specialistsRes, sessionsRes] = await Promise.all([
        apiClient.GET('/api/rooms'),
        apiClient.GET('/api/specialists'),
        apiClient.GET('/api/sessions', {
          params: { query: { date: selectedDate } },
        }),
      ]);

      if (roomsRes.error) {
        throw new Error('Failed to load rooms');
      }
      if (sessionsRes.error) {
        throw new Error('Failed to load sessions');
      }

      setRooms(roomsRes.data || []);
      setSpecialists(specialistsRes.data || []);
      setSessions(sessionsRes.data || []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error loading schedule');
    } finally {
      setLoading(false);
    }
  }, [selectedDate]);

  useEffect(() => {
    fetchBoardData();
  }, [fetchBoardData, refreshTrigger]);

  const handlePrevDay = () => {
    onDateChange(shiftDate(selectedDate, -1));
  };

  const handleNextDay = () => {
    onDateChange(shiftDate(selectedDate, 1));
  };

  const handleToday = () => {
    onDateChange(getTodayIso());
  };

  const handleStatusUpdate = async (sessionId: number, targetStatus: 'done' | 'cancelled') => {
    setActionError(null);
    try {
      const { data, error: patchErr, response } = await apiClient.PATCH(
        '/api/sessions/{session_id}',
        {
          params: { path: { session_id: sessionId } },
          body: { status: targetStatus },
        }
      );

      if (patchErr) {
        const traceId = response.headers.get('x-trace-id');
        const traceSuffix = traceId ? ` (Trace ID: ${traceId})` : '';
        const detailMsg = (patchErr as { detail?: string }).detail || 'Failed to update status';
        setActionError(`${detailMsg}${traceSuffix}`);
        return;
      }

      if (data) {
        setSessions((prev) =>
          prev.map((s) => (s.id === sessionId ? { ...s, status: data.status } : s))
        );
      }
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Network error updating session');
    }
  };

  const workingSpecialists = useMemo(() => {
    const map = new Map<number, { id: number; name: string; count: number }>();
    for (const s of sessions) {
      const existing = map.get(s.specialist_id);
      if (existing) {
        existing.count += 1;
      } else {
        map.set(s.specialist_id, {
          id: s.specialist_id,
          name: s.specialist_name,
          count: 1,
        });
      }
    }
    return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name));
  }, [sessions]);

  const kpi = useMemo(() => {
    const total = sessions.length;
    const planned = sessions.filter((s) => s.status === 'planned').length;
    const done = sessions.filter((s) => s.status === 'done').length;
    const cancelled = sessions.filter((s) => s.status === 'cancelled').length;
    const activeMinutes = sessions
      .filter((s) => s.status !== 'cancelled')
      .reduce((acc, s) => acc + s.duration_minutes, 0);
    const capacityMinutes = rooms.length * TOTAL_WORK_MINUTES;
    const utilizationPct =
      capacityMinutes > 0 ? Math.min(100, Math.round((activeMinutes / capacityMinutes) * 100)) : 0;

    return { total, planned, done, cancelled, utilizationPct };
  }, [sessions, rooms.length]);

  const visibleSessions = useMemo(() => {
    if (statusFilter === 'all') return sessions;
    return sessions.filter((s) => s.status === statusFilter);
  }, [sessions, statusFilter]);

  const ganttRows = useMemo(() => {
    if (ganttGroupBy === 'room') {
      return rooms.map((r) => ({
        id: r.id,
        title: r.name,
        subtitle: 'Room',
      }));
    }

    const rowMap = new Map<number, { id: number; title: string; subtitle: string }>();
    for (const sp of specialists) {
      rowMap.set(sp.id, { id: sp.id, title: sp.name, subtitle: sp.specialty });
    }
    for (const s of sessions) {
      if (!rowMap.has(s.specialist_id)) {
        rowMap.set(s.specialist_id, {
          id: s.specialist_id,
          title: s.specialist_name,
          subtitle: 'Specialist',
        });
      }
    }
    return Array.from(rowMap.values()).sort((a, b) => a.title.localeCompare(b.title));
  }, [ganttGroupBy, rooms, specialists, sessions]);

  const drawerSession = useMemo(
    () => (drawerSessionId !== null ? sessions.find((s) => s.id === drawerSessionId) || null : null),
    [drawerSessionId, sessions]
  );

  const isTodaySelected = selectedDate === getTodayIso();
  const showNowMarker =
    isTodaySelected &&
    nowClock.minutes >= WORK_START_MINUTES &&
    nowClock.minutes <= WORK_END_MINUTES;
  const nowMarkerLeftPct = ((nowClock.minutes - WORK_START_MINUTES) / TOTAL_WORK_MINUTES) * 100;

  return (
    <div className="space-y-5">
      {/* Print Isolation Styles */}
      <style>{`
        @media print {
          .no-print {
            display: none !important;
          }
          body {
            background: #ffffff !important;
          }
        }
      `}</style>

      {/* Top Control Header */}
      <div className="no-print bg-white p-4 rounded-2xl border border-slate-200/90 shadow-xs space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <h2 className="text-lg font-bold text-slate-900 tracking-tight">Day Board</h2>
              <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2.5 py-0.5 rounded-full">
                {formatReadableDate(selectedDate)}
              </span>
              {nowClock.label && (
                <span className="text-[11px] font-mono tabular-nums px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-100 inline-flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {nowClock.label}
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Track studio room utilization, inspect schedules on the timeline, and book conflict-free sessions.
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {/* View Mode Toggle */}
            <div className="flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200/70">
              <button
                type="button"
                data-testid="view-mode-columns"
                onClick={() => setViewMode('columns')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                  viewMode === 'columns'
                    ? 'bg-white text-indigo-700 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <LayoutGrid className="w-3.5 h-3.5" />
                Columns
              </button>
              <button
                type="button"
                data-testid="view-mode-gantt"
                onClick={() => setViewMode('gantt')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                  viewMode === 'gantt'
                    ? 'bg-white text-indigo-700 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <GanttChart className="w-3.5 h-3.5" />
                Gantt Timeline
              </button>
            </div>

            <button
              type="button"
              onClick={fetchBoardData}
              disabled={loading}
              className="h-9 w-9 flex items-center justify-center rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 transition disabled:opacity-50"
              title="Refresh schedule"
            >
              <RotateCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>

            <button
              type="button"
              onClick={() => window.print()}
              className="h-9 px-3 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold flex items-center gap-1.5 transition"
              title="Print day schedule"
            >
              <Printer className="w-3.5 h-3.5" />
              Print
            </button>

            <button
              type="button"
              data-testid="btn-new-session"
              onClick={() => onOpenBookingModal({ date: selectedDate })}
              className="h-9 flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white px-4 rounded-xl text-xs font-semibold shadow-xs transition"
            >
              <Plus className="w-4 h-4" />
              New Session
            </button>
          </div>
        </div>

        {/* Date Navigation Row */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-100">
          <div className="flex items-center gap-2 flex-wrap">
            <button
              type="button"
              data-testid="btn-prev-day"
              onClick={handlePrevDay}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              Prev
            </button>
            <button
              type="button"
              data-testid="btn-today"
              onClick={handleToday}
              className="px-3 py-1.5 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition"
            >
              Today
            </button>
            <button
              type="button"
              data-testid="btn-next-day"
              onClick={handleNextDay}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition"
            >
              Next
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
            <div className="flex items-center gap-2 ml-1 pl-3 border-l border-slate-200">
              <Calendar className="w-4 h-4 text-slate-400" />
              <input
                type="date"
                data-testid="date-picker"
                value={selectedDate}
                onChange={(e) => onDateChange(e.target.value)}
                className="border border-slate-300 rounded-lg px-2.5 py-1 text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>

          {/* Status Filter Pills */}
          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-slate-400 font-medium mr-1 inline-flex items-center gap-1">
              <Filter className="w-3.5 h-3.5" />
              Status:
            </span>
            {(['all', 'planned', 'done', 'cancelled'] as StatusFilter[]).map((st) => (
              <button
                key={st}
                type="button"
                data-testid={`status-filter-${st}`}
                onClick={() => setStatusFilter(st)}
                className={`px-2.5 py-1 rounded-lg capitalize font-medium transition ${
                  statusFilter === st
                    ? 'bg-slate-900 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {st}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* KPI Summary Ribbon */}
      <div
        data-testid="kpi-ribbon"
        className="no-print grid grid-cols-2 sm:grid-cols-5 gap-3"
      >
        <div className="bg-white rounded-xl border border-slate-200/90 p-3.5 shadow-2xs">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block">
            Total Sessions
          </span>
          <span
            data-testid="kpi-total"
            className="text-xl font-bold text-slate-900 font-mono tabular-nums mt-0.5 block"
          >
            {kpi.total}
          </span>
        </div>

        <div className="bg-white rounded-xl border border-slate-200/90 p-3.5 shadow-2xs">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-indigo-500 block">
            Planned
          </span>
          <span
            data-testid="kpi-planned"
            className="text-xl font-bold text-indigo-700 font-mono tabular-nums mt-0.5 block"
          >
            {kpi.planned}
          </span>
        </div>

        <div className="bg-white rounded-xl border border-slate-200/90 p-3.5 shadow-2xs">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-emerald-600 block">
            Completed
          </span>
          <span
            data-testid="kpi-done"
            className="text-xl font-bold text-emerald-700 font-mono tabular-nums mt-0.5 block"
          >
            {kpi.done}
          </span>
        </div>

        <div className="bg-white rounded-xl border border-slate-200/90 p-3.5 shadow-2xs">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block">
            Cancelled
          </span>
          <span
            data-testid="kpi-cancelled"
            className="text-xl font-bold text-slate-500 font-mono tabular-nums mt-0.5 block"
          >
            {kpi.cancelled}
          </span>
        </div>

        <div className="bg-white rounded-xl border border-slate-200/90 p-3.5 shadow-2xs col-span-2 sm:col-span-1 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Studio Load
            </span>
            <Activity className="w-3.5 h-3.5 text-indigo-500" />
          </div>
          <div>
            <span
              data-testid="kpi-utilization"
              className="text-xl font-bold text-slate-900 font-mono tabular-nums block"
            >
              {kpi.utilizationPct}%
            </span>
            <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden mt-1.5">
              <div
                className="h-full bg-indigo-600 rounded-full transition-all duration-300"
                style={{ width: `${kpi.utilizationPct}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Quick Specialist Filter Bar */}
      {sessions.length > 0 && (
        <div
          data-testid="specialist-filter-bar"
          className="no-print bg-white border border-slate-200/90 px-3.5 py-2.5 rounded-xl flex items-center gap-2 overflow-x-auto shadow-2xs"
        >
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 shrink-0 pr-1">
            Specialist:
          </span>
          <button
            type="button"
            data-testid="filter-specialist-all"
            onClick={() => setSelectedSpecialistId(null)}
            className={`px-3 py-1 rounded-lg text-xs font-semibold shrink-0 transition ${
              selectedSpecialistId === null
                ? 'bg-indigo-600 text-white shadow-2xs'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            All Specialists ({sessions.length})
          </button>
          {workingSpecialists.map((sp) => {
            const isSelected = selectedSpecialistId === sp.id;
            const theme = getSpecialtyTheme(sp.name);
            return (
              <button
                key={sp.id}
                type="button"
                data-testid={`filter-specialist-${sp.id}`}
                onClick={() => setSelectedSpecialistId(isSelected ? null : sp.id)}
                className={`px-3 py-1 rounded-lg text-xs font-semibold shrink-0 transition inline-flex items-center gap-1.5 ${
                  isSelected
                    ? 'bg-indigo-600 text-white shadow-2xs'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                <span
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: isSelected ? '#ffffff' : theme.accentColor }}
                />
                <span>
                  {sp.name} ({sp.count})
                </span>
              </button>
            );
          })}
        </div>
      )}

      {actionError && (
        <div
          data-testid="action-error-banner"
          className="no-print p-3 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm flex items-center gap-2"
        >
          <AlertCircle className="w-4 h-4 shrink-0 text-red-500" />
          <span>{actionError}</span>
        </div>
      )}

      {error && (
        <div
          data-testid="fetch-error-banner"
          className="no-print p-4 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm flex items-center gap-2"
        >
          <AlertCircle className="w-5 h-5 shrink-0 text-red-500" />
          <span>{error}</span>
        </div>
      )}

      {/* Printable Header */}
      <div className="hidden print:block pb-3 border-b border-slate-300">
        <h1 className="text-lg font-bold text-black">SessionBoard — Daily Studio Schedule</h1>
        <p className="text-xs text-slate-700">
          {formatReadableDate(selectedDate)} ({selectedDate}) • Total: {kpi.total} (Planned:{' '}
          {kpi.planned}, Done: {kpi.done}, Cancelled: {kpi.cancelled})
        </p>
      </div>

      {/* Main Board Area */}
      {loading ? (
        <div className="bg-white rounded-2xl border border-slate-200 py-16 text-center text-slate-400 text-sm">
          Loading day schedule...
        </div>
      ) : viewMode === 'columns' ? (
        /* VIEW 1: ROOM COLUMNS */
        <div
          className={`grid grid-cols-1 gap-4 ${
            rooms.length >= 4
              ? 'md:grid-cols-2 xl:grid-cols-[repeat(auto-fit,minmax(250px,1fr))]'
              : 'md:grid-cols-3'
          }`}
        >
          {rooms.map((room) => {
            const roomSessions = visibleSessions.filter((s) => s.room_id === room.id);
            return (
              <div
                key={room.id}
                data-testid={`room-column-${room.id}`}
                className="bg-white rounded-2xl border border-slate-200/90 shadow-sm p-3.5 flex flex-col min-h-[360px] min-w-0"
              >
                <div className="flex items-center justify-between gap-2 pb-3 border-b border-slate-100">
                  <div className="flex items-center gap-2 min-w-0">
                    <DoorOpen className="w-4 h-4 text-indigo-600 shrink-0" />
                    <h3 className="font-bold text-slate-800 text-[15px] truncate" title={room.name}>
                      {room.name}
                    </h3>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <span
                      title={`${roomSessions.length} ${roomSessions.length === 1 ? 'session' : 'sessions'}`}
                      className="text-[11px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-semibold font-mono"
                    >
                      {roomSessions.length}
                    </span>
                    <button
                      type="button"
                      onClick={() => onOpenBookingModal({ roomId: room.id, date: selectedDate })}
                      className="no-print p-1 rounded-lg text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 transition"
                      title={`Book in ${room.name}`}
                    >
                      <Plus className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <div className="py-4 space-y-3 flex-1">
                  {roomSessions.length === 0 ? (
                    <div className="py-12 text-center text-sm text-slate-400 italic border border-dashed border-slate-200 rounded-xl">
                      No sessions scheduled
                    </div>
                  ) : (
                    roomSessions.map((session) => {
                      const isPlanned = session.status === 'planned';
                      const isDone = session.status === 'done';
                      const isCancelled = session.status === 'cancelled';
                      const theme = getSpecialtyTheme(session.specialist_name);

                      const isSelectedSpecialist =
                        selectedSpecialistId !== null &&
                        session.specialist_id === selectedSpecialistId;
                      const isOtherSpecialist =
                        selectedSpecialistId !== null &&
                        session.specialist_id !== selectedSpecialistId;

                      return (
                        <div
                          key={session.id}
                          data-testid={`session-card-${session.id}`}
                          onClick={() => setDrawerSessionId(session.id)}
                          style={{
                            borderLeftWidth: '3px',
                            borderLeftColor: isCancelled ? '#cbd5e1' : theme.accentColor,
                          }}
                          className={`p-3.5 rounded-xl border transition cursor-pointer ${
                            isCancelled
                              ? 'bg-slate-50 border-slate-200 opacity-60 text-slate-500'
                              : isDone
                              ? 'bg-emerald-50/40 border-emerald-200 shadow-2xs hover:border-emerald-300'
                              : 'bg-white border-slate-200 shadow-xs hover:border-indigo-300 hover:shadow-sm'
                          } ${isOtherSpecialist ? 'opacity-30 hover:opacity-75' : ''} ${
                            isSelectedSpecialist ? 'ring-2 ring-indigo-500/40 shadow-sm' : ''
                          }`}
                        >
                          <div className="flex flex-wrap items-center justify-between gap-1.5 mb-2">
                            <div className="flex items-center gap-1 text-xs font-semibold text-slate-700 font-mono tabular-nums whitespace-nowrap">
                              <Clock className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                              <span>
                                {session.start_time}–{session.end_time}
                              </span>
                              <span className="text-[11px] text-slate-400 font-sans font-normal">
                                ({session.duration_minutes}m)
                              </span>
                            </div>
                            <span
                              data-testid={`session-status-${session.id}`}
                              className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider shrink-0 ${
                                isPlanned
                                  ? 'bg-indigo-50 text-indigo-700 border border-indigo-100'
                                  : isDone
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : 'bg-slate-200 text-slate-600'
                              }`}
                            >
                              {session.status}
                            </span>
                          </div>

                          <div className="space-y-1.5 text-sm">
                            <div className="font-semibold text-slate-900 flex items-center gap-2">
                              <span
                                className={`w-6 h-6 rounded-full text-[10px] font-bold flex items-center justify-center shrink-0 ${theme.avatarBg} ${theme.avatarText}`}
                              >
                                {getInitials(session.specialist_name)}
                              </span>
                              <span className={isCancelled ? 'line-through' : ''}>
                                {session.specialist_name}
                              </span>
                            </div>
                            <div className="text-xs text-slate-500 pl-8 flex items-center gap-1">
                              <User className="w-3 h-3 text-slate-400 shrink-0" />
                              <span>Client:</span>
                              <span className="text-slate-700 font-medium">
                                {session.client_display_name}
                              </span>
                            </div>
                          </div>

                          {isPlanned && (
                            <div className="no-print mt-3 pt-2.5 border-t border-slate-100 flex items-center gap-2">
                              <button
                                type="button"
                                data-testid={`btn-done-${session.id}`}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleStatusUpdate(session.id, 'done');
                                }}
                                className="flex-1 flex items-center justify-center gap-1 px-2.5 py-1 text-xs font-semibold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded-lg transition"
                              >
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                Done
                              </button>
                              <button
                                type="button"
                                data-testid={`btn-cancel-${session.id}`}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleStatusUpdate(session.id, 'cancelled');
                                }}
                                className="flex-1 flex items-center justify-center gap-1 px-2.5 py-1 text-xs font-semibold text-slate-600 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg transition"
                              >
                                <XCircle className="w-3.5 h-3.5" />
                                Cancel
                              </button>
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* VIEW 2: GANTT TIMELINE */
        <div
          data-testid="gantt-timeline-view"
          className="bg-white rounded-2xl border border-slate-200/90 shadow-xs overflow-hidden"
        >
          {/* Gantt Sub-toolbar */}
          <div className="no-print px-4 py-3 border-b border-slate-100 flex flex-wrap items-center justify-between gap-3 bg-slate-50/70">
            <div className="flex items-center gap-1.5 bg-white p-1 rounded-xl border border-slate-200">
              <button
                type="button"
                data-testid="gantt-group-room"
                onClick={() => setGanttGroupBy('room')}
                className={`px-3 py-1 rounded-lg text-xs font-semibold transition ${
                  ganttGroupBy === 'room'
                    ? 'bg-indigo-600 text-white shadow-2xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                By Room
              </button>
              <button
                type="button"
                data-testid="gantt-group-specialist"
                onClick={() => setGanttGroupBy('specialist')}
                className={`px-3 py-1 rounded-lg text-xs font-semibold transition ${
                  ganttGroupBy === 'specialist'
                    ? 'bg-indigo-600 text-white shadow-2xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                By Specialist
              </button>
            </div>

            <div className="text-xs text-slate-500 flex items-center gap-3">
              <span>Studio hours: 08:00–20:00</span>
              <span className="hidden sm:inline text-slate-300">•</span>
              <span className="hidden sm:inline">
                Click any open slot to book, or click a block to inspect
              </span>
            </div>
          </div>

          {/* Gantt Scroll Container */}
          <div className="overflow-x-auto">
            <div className="min-w-[920px]">
              {/* Time Scale Header */}
              <div className="flex border-b border-slate-200 bg-slate-50/50">
                <div className="w-48 shrink-0 px-4 py-2.5 text-xs font-bold uppercase tracking-wider text-slate-500 border-r border-slate-200">
                  {ganttGroupBy === 'room' ? 'Room' : 'Specialist'}
                </div>
                <div className="flex-1 grid grid-cols-12 relative">
                  {GANTT_HOURS.map((hour) => (
                    <div
                      key={hour}
                      className="px-2 py-2.5 text-[11px] font-mono font-semibold text-slate-500 border-r border-slate-100 last:border-r-0"
                    >
                      {hour}
                    </div>
                  ))}
                  <span className="absolute right-1.5 top-2.5 text-[10px] font-mono text-slate-400">
                    20:00
                  </span>
                </div>
              </div>

              {/* Gantt Tracks */}
              {ganttRows.length === 0 ? (
                <div className="py-12 text-center text-sm text-slate-400 italic">
                  No {ganttGroupBy === 'room' ? 'rooms' : 'specialists'} registered
                </div>
              ) : (
                <div className="divide-y divide-slate-100">
                  {ganttRows.map((row) => {
                    const rowSessions = visibleSessions.filter((s) =>
                      ganttGroupBy === 'room' ? s.room_id === row.id : s.specialist_id === row.id
                    );
                    const activeMinutes = rowSessions
                      .filter((s) => s.status !== 'cancelled')
                      .reduce((sum, s) => sum + s.duration_minutes, 0);

                    return (
                      <div key={row.id} className="flex items-stretch hover:bg-slate-50/40">
                        {/* Row Label */}
                        <div className="w-48 shrink-0 px-4 py-3 border-r border-slate-200 flex flex-col justify-center">
                          <div className="text-sm font-semibold text-slate-900 truncate">
                            {row.title}
                          </div>
                          <div className="text-[11px] text-slate-500 flex items-center justify-between mt-0.5">
                            <span className="truncate">{row.subtitle}</span>
                            <span className="font-mono text-slate-600 font-medium">
                              {rowSessions.length} • {activeMinutes}m
                            </span>
                          </div>
                        </div>

                        {/* Interactive Timeline Track */}
                        <div className="flex-1 relative h-20">
                          {/* Clickable Hour Slots */}
                          <div className="grid grid-cols-12 h-full">
                            {GANTT_HOURS.map((hourStr) => (
                              <button
                                key={hourStr}
                                type="button"
                                data-testid={`gantt-slot-${row.id}-${hourStr}`}
                                onClick={() =>
                                  onOpenBookingModal(
                                    ganttGroupBy === 'room'
                                      ? { roomId: row.id, startTime: hourStr, date: selectedDate }
                                      : {
                                          specialistId: row.id,
                                          startTime: hourStr,
                                          date: selectedDate,
                                        }
                                  )
                                }
                                title={`Click to book ${row.title} at ${hourStr}`}
                                className="h-full border-r border-slate-100 last:border-r-0 hover:bg-indigo-50/70 transition-colors flex items-center justify-center group"
                              >
                                <span className="opacity-0 group-hover:opacity-100 text-[10px] font-semibold text-indigo-600 bg-white/90 px-1.5 py-0.5 rounded shadow-2xs pointer-events-none">
                                  + {hourStr}
                                </span>
                              </button>
                            ))}
                          </div>

                          {/* Current Time Indicator */}
                          {showNowMarker && (
                            <div
                              className="absolute top-0 bottom-0 w-0.5 bg-rose-500 z-20 pointer-events-none"
                              style={{ left: `${nowMarkerLeftPct}%` }}
                            >
                              <span className="w-2 h-2 rounded-full bg-rose-500 -ml-[3px] -mt-1 block" />
                            </div>
                          )}

                          {/* Positioned Session Blocks */}
                          {rowSessions.map((session) => {
                            const startMin = timeToMinutes(session.start_time);
                            const leftPct = Math.max(
                              0,
                              ((startMin - WORK_START_MINUTES) / TOTAL_WORK_MINUTES) * 100
                            );
                            const widthPct = Math.min(
                              100 - leftPct,
                              (session.duration_minutes / TOTAL_WORK_MINUTES) * 100
                            );
                            const theme = getSpecialtyTheme(session.specialist_name);
                            const isCancelled = session.status === 'cancelled';
                            const isDone = session.status === 'done';
                            const isOtherSpecialist =
                              selectedSpecialistId !== null &&
                              session.specialist_id !== selectedSpecialistId;

                            return (
                              <button
                                key={session.id}
                                type="button"
                                data-testid={`gantt-session-${session.id}`}
                                onClick={() => setDrawerSessionId(session.id)}
                                style={{
                                  left: `${leftPct}%`,
                                  width: `${widthPct}%`,
                                  borderLeftWidth: '3px',
                                  borderLeftColor: isCancelled ? '#94a3b8' : theme.accentColor,
                                }}
                                title={`${session.start_time}–${session.end_time} • ${session.client_display_name} (${session.specialist_name}, ${session.room_name})`}
                                className={`absolute top-2 bottom-2 z-10 rounded-lg border px-2 py-1 text-left overflow-hidden shadow-2xs transition flex flex-col justify-between ${
                                  isCancelled
                                    ? 'bg-slate-100 border-slate-200 opacity-60 text-slate-500'
                                    : isDone
                                    ? 'bg-emerald-50 border-emerald-300 text-emerald-950 hover:shadow-sm'
                                    : `${theme.ganttBg} ${theme.ganttBorder} text-slate-900 hover:shadow-sm`
                                } ${isOtherSpecialist ? 'opacity-30 hover:opacity-80' : ''}`}
                              >
                                <div className="flex items-center justify-between gap-1 text-[10px] font-mono font-bold">
                                  <span className="truncate">
                                    {session.start_time}–{session.end_time}
                                  </span>
                                  <span className="uppercase text-[9px] shrink-0 opacity-75">
                                    {session.status}
                                  </span>
                                </div>
                                <div className="text-xs font-semibold truncate">
                                  {session.client_display_name}
                                </div>
                                <div className="text-[10px] text-slate-600 truncate">
                                  {ganttGroupBy === 'room'
                                    ? session.specialist_name
                                    : session.room_name}
                                </div>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Slide-Over Session Detail Drawer */}
      {drawerSession && (
        <>
          <div
            className="fixed inset-0 bg-slate-950/35 backdrop-blur-sm z-40 no-print"
            onClick={() => setDrawerSessionId(null)}
          />
          <aside
            data-testid="session-drawer"
            role="dialog"
            aria-label="Session details"
            className="fixed inset-y-0 right-0 z-50 w-full max-w-md bg-white shadow-2xl border-l border-slate-200 flex flex-col no-print"
          >
            {/* Drawer Header */}
            <div className="px-5 py-4 border-b border-slate-200 flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-semibold text-slate-400">
                    Session #{drawerSession.id}
                  </span>
                  <span
                    className={`text-[11px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider ${
                      drawerSession.status === 'planned'
                        ? 'bg-indigo-50 text-indigo-700 border border-indigo-100'
                        : drawerSession.status === 'done'
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-slate-200 text-slate-600'
                    }`}
                  >
                    {drawerSession.status}
                  </span>
                </div>
                <h3 className="text-lg font-bold text-slate-900 mt-1">
                  {drawerSession.client_display_name}
                </h3>
                <p className="text-xs text-slate-500">
                  {formatReadableDate(drawerSession.session_date)}
                </p>
              </div>
              <button
                type="button"
                data-testid="btn-close-drawer"
                onClick={() => setDrawerSessionId(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Drawer Body */}
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 space-y-3">
                <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Time & Location
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-600 flex items-center gap-2">
                    <Clock className="w-4 h-4 text-indigo-600" />
                    Time Slot
                  </span>
                  <span className="font-mono font-semibold text-slate-900">
                    {drawerSession.start_time}–{drawerSession.end_time} ({drawerSession.duration_minutes}m)
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-600 flex items-center gap-2">
                    <DoorOpen className="w-4 h-4 text-indigo-600" />
                    Room
                  </span>
                  <span className="font-semibold text-slate-900">{drawerSession.room_name}</span>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-white border border-slate-200 space-y-3">
                <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Assigned Participants
                </div>
                <div className="flex items-center gap-3">
                  {(() => {
                    const theme = getSpecialtyTheme(drawerSession.specialist_name);
                    return (
                      <span
                        className={`w-9 h-9 rounded-full text-xs font-bold flex items-center justify-center shrink-0 ${theme.avatarBg} ${theme.avatarText}`}
                      >
                        {getInitials(drawerSession.specialist_name)}
                      </span>
                    );
                  })()}
                  <div>
                    <div className="text-sm font-semibold text-slate-900">
                      {drawerSession.specialist_name}
                    </div>
                    <div className="text-xs text-slate-500">Assigned Specialist</div>
                  </div>
                </div>
                <div className="pt-2 border-t border-slate-100 flex items-center gap-3">
                  <span className="w-9 h-9 rounded-full bg-slate-100 text-slate-700 text-xs font-bold flex items-center justify-center shrink-0">
                    {getInitials(drawerSession.client_display_name)}
                  </span>
                  <div>
                    <div className="text-sm font-semibold text-slate-900">
                      {drawerSession.client_display_name}
                    </div>
                    <div className="text-xs text-slate-500">Client</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Drawer Footer */}
            <div className="p-5 border-t border-slate-200 bg-slate-50 space-y-2.5">
              {drawerSession.status === 'planned' && (
                <div className="grid grid-cols-2 gap-2.5">
                  <button
                    type="button"
                    onClick={() => handleStatusUpdate(drawerSession.id, 'done')}
                    className="flex items-center justify-center gap-1.5 py-2.5 px-3 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs transition"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    Mark Done
                  </button>
                  <button
                    type="button"
                    onClick={() => handleStatusUpdate(drawerSession.id, 'cancelled')}
                    className="flex items-center justify-center gap-1.5 py-2.5 px-3 rounded-xl text-xs font-semibold bg-white hover:bg-rose-50 text-rose-700 border border-rose-200 transition"
                  >
                    <XCircle className="w-4 h-4" />
                    Cancel Session
                  </button>
                </div>
              )}

              <button
                type="button"
                data-testid="btn-book-followup"
                onClick={() => {
                  const target = drawerSession;
                  setDrawerSessionId(null);
                  onOpenBookingModal({
                    specialistId: target.specialist_id,
                    clientId: target.client_id,
                    roomId: target.room_id,
                    date: selectedDate,
                  });
                }}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs transition"
              >
                <CalendarPlus className="w-4 h-4" />
                Book Follow-up Session
              </button>
            </div>
          </aside>
        </>
      )}
    </div>
  );
};
