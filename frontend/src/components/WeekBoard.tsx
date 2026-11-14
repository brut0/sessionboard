import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  CalendarRange,
  ChevronLeft,
  ChevronRight,
  Clock,
  Plus,
  Users,
  DoorOpen,
  ArrowUpRight,
  AlertCircle,
  RotateCw,
} from 'lucide-react';
import { apiClient, type Room, type Session } from '../api/client';
import { getWeekDays, shiftDate, getTodayIso } from '../utils/time';
import { getSpecialtyTheme } from '../utils/theme';
import type { BookingPrefill } from './DayBoard';

interface WeekBoardProps {
  selectedDate: string;
  onDateChange: (date: string) => void;
  onSelectDayView: (date: string) => void;
  onOpenBookingModal: (prefill?: BookingPrefill) => void;
  refreshTrigger?: number;
}

export const WeekBoard: React.FC<WeekBoardProps> = ({
  selectedDate,
  onDateChange,
  onSelectDayView,
  onOpenBookingModal,
  refreshTrigger = 0,
}) => {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [sessionsByDate, setSessionsByDate] = useState<Record<string, Session[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDayIndex, setSelectedDayIndex] = useState<number | 'all'>('all');

  const weekDays = useMemo(() => getWeekDays(selectedDate), [selectedDate]);
  const todayIso = getTodayIso();

  const fetchWeekData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [roomsRes, ...dayResponses] = await Promise.all([
        apiClient.GET('/api/rooms'),
        ...weekDays.map((day) =>
          apiClient.GET('/api/sessions', {
            params: { query: { date: day.date } },
          })
        ),
      ]);

      if (roomsRes.error) {
        throw new Error('Failed to load rooms');
      }

      const nextMap: Record<string, Session[]> = {};
      weekDays.forEach((day, idx) => {
        const res = dayResponses[idx];
        if (res.error) {
          throw new Error(`Failed to load sessions for ${day.date}`);
        }
        const daySessions = (res.data || [])
          .filter((s) => s.session_date === day.date)
          .sort((a, b) => a.start_time.localeCompare(b.start_time));
        nextMap[day.date] = daySessions;
      });

      setRooms(roomsRes.data || []);
      setSessionsByDate(nextMap);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error loading week overview');
    } finally {
      setLoading(false);
    }
  }, [weekDays]);

  useEffect(() => {
    fetchWeekData();
  }, [fetchWeekData, refreshTrigger]);

  const allWeekSessions = useMemo(
    () => weekDays.flatMap((d) => sessionsByDate[d.date] || []),
    [weekDays, sessionsByDate]
  );

  const weekStats = useMemo(() => {
    const total = allWeekSessions.length;
    const planned = allWeekSessions.filter((s) => s.status === 'planned').length;
    const done = allWeekSessions.filter((s) => s.status === 'done').length;
    const activeSpecialists = new Set(allWeekSessions.map((s) => s.specialist_id)).size;

    let busiestLabel = '—';
    let maxCount = 0;
    for (const day of weekDays) {
      const count = (sessionsByDate[day.date] || []).length;
      if (count > maxCount) {
        maxCount = count;
        busiestLabel = `${day.shortName} (${count})`;
      }
    }

    return { total, planned, done, activeSpecialists, busiestLabel };
  }, [allWeekSessions, weekDays, sessionsByDate]);

  const weekRangeLabel = useMemo(() => {
    if (weekDays.length < 7) return '';
    const first = weekDays[0];
    const last = weekDays[6];
    const year = last.date.slice(0, 4);
    return `${first.monthShort} ${first.dayNumber} – ${last.monthShort} ${last.dayNumber}, ${year}`;
  }, [weekDays]);

  const activeDay = selectedDayIndex === 'all' ? null : weekDays[selectedDayIndex];
  const activeDaySessions = activeDay ? sessionsByDate[activeDay.date] || [] : [];

  return (
    <div data-testid="week-board" className="space-y-5">
      {/* Header & Week Controls */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-xs space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <h2 className="text-lg font-bold text-slate-900 tracking-tight">Week Overview</h2>
              <span className="text-xs font-medium text-indigo-700 bg-indigo-50 border border-indigo-100 px-2.5 py-0.5 rounded-full inline-flex items-center gap-1.5">
                <CalendarRange className="w-3.5 h-3.5" />
                {weekRangeLabel}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Inspect 7-day booking density across Monday–Sunday and drill into any day or room.
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <button
              type="button"
              data-testid="btn-prev-week"
              onClick={() => onDateChange(shiftDate(selectedDate, -7))}
              className="h-9 px-3 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-xl inline-flex items-center gap-1 transition"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              Prev Week
            </button>
            <button
              type="button"
              data-testid="btn-this-week"
              onClick={() => onDateChange(todayIso)}
              className="h-9 px-3 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-xl transition"
            >
              This Week
            </button>
            <button
              type="button"
              data-testid="btn-next-week"
              onClick={() => onDateChange(shiftDate(selectedDate, 7))}
              className="h-9 px-3 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-xl inline-flex items-center gap-1 transition"
            >
              Next Week
              <ChevronRight className="w-3.5 h-3.5" />
            </button>

            <button
              type="button"
              onClick={fetchWeekData}
              disabled={loading}
              className="h-9 w-9 flex items-center justify-center rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 transition disabled:opacity-50"
              title="Refresh week"
            >
              <RotateCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>

            <button
              type="button"
              onClick={() => onOpenBookingModal({ date: activeDay ? activeDay.date : selectedDate })}
              className="h-9 flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white px-4 rounded-xl text-xs font-semibold shadow-xs transition"
            >
              <Plus className="w-4 h-4" />
              New Session
            </button>
          </div>
        </div>

        {/* Day Switcher Pills (Whole Week + Mon..Sun) */}
        <div className="pt-3 border-t border-slate-100 flex items-center gap-1.5 overflow-x-auto">
          <button
            type="button"
            data-testid="week-filter-all"
            onClick={() => setSelectedDayIndex('all')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold shrink-0 inline-flex items-center gap-1.5 transition ${
              selectedDayIndex === 'all'
                ? 'bg-indigo-600 text-white shadow-2xs'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            <span>Whole Week</span>
            <span
              className={`px-1.5 py-0.5 rounded-md text-[10px] font-mono ${
                selectedDayIndex === 'all'
                  ? 'bg-indigo-500 text-white'
                  : 'bg-white text-slate-700'
              }`}
            >
              {weekStats.total}
            </span>
          </button>

          {weekDays.map((day, idx) => {
            const count = (sessionsByDate[day.date] || []).length;
            const isSelected = selectedDayIndex === idx;
            const isToday = day.date === todayIso;

            return (
              <button
                key={day.date}
                type="button"
                data-testid={`week-day-pill-${idx}`}
                onClick={() => setSelectedDayIndex(idx)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold shrink-0 inline-flex items-center gap-1.5 transition ${
                  isSelected
                    ? 'bg-slate-900 text-white shadow-2xs'
                    : isToday
                    ? 'bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                <span>
                  {day.shortName} {day.dayNumber}
                </span>
                <span
                  className={`px-1.5 py-0.5 rounded-md text-[10px] font-mono ${
                    isSelected
                      ? 'bg-slate-700 text-white'
                      : 'bg-white/90 text-slate-700'
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Weekly KPI Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <div className="bg-white rounded-xl border border-slate-200/90 p-3.5 shadow-2xs">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block">
            Week Sessions
          </span>
          <span className="text-xl font-bold text-slate-900 font-mono tabular-nums mt-0.5 block">
            {weekStats.total}
          </span>
        </div>
        <div className="bg-white rounded-xl border border-slate-200/90 p-3.5 shadow-2xs">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-indigo-500 block">
            Planned
          </span>
          <span className="text-xl font-bold text-indigo-700 font-mono tabular-nums mt-0.5 block">
            {weekStats.planned}
          </span>
        </div>
        <div className="bg-white rounded-xl border border-slate-200/90 p-3.5 shadow-2xs">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-emerald-600 block">
            Completed
          </span>
          <span className="text-xl font-bold text-emerald-700 font-mono tabular-nums mt-0.5 block">
            {weekStats.done}
          </span>
        </div>
        <div className="bg-white rounded-xl border border-slate-200/90 p-3.5 shadow-2xs">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block">
            Active Specialists
          </span>
          <span className="text-xl font-bold text-slate-900 font-mono tabular-nums mt-0.5 block">
            {weekStats.activeSpecialists}
          </span>
        </div>
        <div className="bg-white rounded-xl border border-slate-200/90 p-3.5 shadow-2xs col-span-2 sm:col-span-1">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block">
            Busiest Day
          </span>
          <span className="text-base font-bold text-slate-900 mt-1 block truncate">
            {weekStats.busiestLabel}
          </span>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm flex items-center gap-2">
          <AlertCircle className="w-5 h-5 shrink-0 text-red-500" />
          <span>{error}</span>
        </div>
      )}

      {/* Main Week View */}
      {loading ? (
        <div className="bg-white rounded-2xl border border-slate-200 py-16 text-center text-slate-400 text-sm">
          Loading weekly schedule...
        </div>
      ) : selectedDayIndex === 'all' ? (
        /* 7-DAY MATRIX GRID */
        <div
          data-testid="week-matrix-grid"
          className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-7 gap-3"
        >
          {weekDays.map((day) => {
            const daySessions = sessionsByDate[day.date] || [];
            const isToday = day.date === todayIso;
            const isSelected = day.date === selectedDate;

            return (
              <div
                key={day.date}
                className={`bg-white rounded-2xl border shadow-xs flex flex-col min-h-[340px] ${
                  isSelected
                    ? 'border-indigo-300 ring-1 ring-indigo-200'
                    : 'border-slate-200/90'
                }`}
              >
                {/* Day Column Header */}
                <div className="p-3 border-b border-slate-100 flex items-center justify-between gap-1">
                  <button
                    type="button"
                    onClick={() => onSelectDayView(day.date)}
                    className="text-left group min-w-0"
                    title={`Open ${day.fullName} in Day Board`}
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-bold text-slate-900 group-hover:text-indigo-600 transition">
                        {day.shortName}
                      </span>
                      {isToday && (
                        <span className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-700">
                          Today
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-slate-500 font-mono">
                      {day.monthShort} {day.dayNumber}
                    </div>
                  </button>

                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      type="button"
                      onClick={() => onOpenBookingModal({ date: day.date })}
                      className="p-1 rounded-lg text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 transition"
                      title={`Book on ${day.date}`}
                    >
                      <Plus className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => onSelectDayView(day.date)}
                      className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition"
                      title="Open in Day Board"
                    >
                      <ArrowUpRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Day Sessions List */}
                <div className="p-2.5 space-y-2 flex-1">
                  {daySessions.length === 0 ? (
                    <div className="h-28 flex items-center justify-center text-center text-[11px] text-slate-400 italic border border-dashed border-slate-200 rounded-xl p-2">
                      No sessions
                    </div>
                  ) : (
                    daySessions.map((session) => {
                      const theme = getSpecialtyTheme(session.specialist_name);
                      const isCancelled = session.status === 'cancelled';
                      const isDone = session.status === 'done';

                      return (
                        <button
                          key={session.id}
                          type="button"
                          onClick={() => onSelectDayView(day.date)}
                          style={{
                            borderLeftWidth: '3px',
                            borderLeftColor: isCancelled ? '#cbd5e1' : theme.accentColor,
                          }}
                          className={`w-full text-left p-2.5 rounded-xl border transition space-y-1 ${
                            isCancelled
                              ? 'bg-slate-50 border-slate-200 opacity-60'
                              : isDone
                              ? 'bg-emerald-50/40 border-emerald-200 hover:border-emerald-300'
                              : 'bg-white border-slate-200 hover:border-indigo-300 shadow-2xs'
                          }`}
                        >
                          <div className="flex items-center justify-between gap-1 text-[11px] font-mono font-semibold text-slate-700">
                            <span className="truncate">
                              {session.start_time}–{session.end_time}
                            </span>
                            <span className="text-[9px] font-sans font-semibold px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 shrink-0">
                              {session.room_name}
                            </span>
                          </div>
                          <div
                            className={`text-xs font-semibold text-slate-900 truncate ${
                              isCancelled ? 'line-through' : ''
                            }`}
                          >
                            {session.client_display_name}
                          </div>
                          <div className="text-[11px] text-slate-500 truncate">
                            {session.specialist_name}
                          </div>
                        </button>
                      );
                    })
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* SINGLE DAY ROOM GRID WITHIN WEEK VIEW */
        activeDay && (
          <div data-testid="week-single-day-grid" className="space-y-4">
            <div className="bg-white border border-slate-200/90 rounded-2xl px-4 py-3 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <h3 className="text-sm font-bold text-slate-900">
                  {activeDay.fullName}, {activeDay.monthShort} {activeDay.dayNumber}
                </h3>
                <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 font-semibold">
                  {activeDaySessions.length}{' '}
                  {activeDaySessions.length === 1 ? 'session' : 'sessions'}
                </span>
              </div>

              <div className="flex items-center gap-4 text-xs text-slate-500">
                <span className="inline-flex items-center gap-1">
                  <Users className="w-3.5 h-3.5 text-slate-400" />
                  Specialists:{' '}
                  <strong className="text-slate-800">
                    {new Set(activeDaySessions.map((s) => s.specialist_id)).size}
                  </strong>
                </span>
                <span className="inline-flex items-center gap-1">
                  Clients:{' '}
                  <strong className="text-slate-800">
                    {new Set(activeDaySessions.map((s) => s.client_id)).size}
                  </strong>
                </span>
                <button
                  type="button"
                  onClick={() => onSelectDayView(activeDay.date)}
                  className="px-3 py-1.5 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-semibold inline-flex items-center gap-1 transition"
                >
                  Open in Day Board
                  <ArrowUpRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            <div
              className={`grid grid-cols-1 gap-5 ${
                rooms.length >= 4 ? 'md:grid-cols-2 xl:grid-cols-4' : 'md:grid-cols-3'
              }`}
            >
              {rooms.map((room) => {
                const roomSessions = activeDaySessions.filter((s) => s.room_id === room.id);
                return (
                  <div
                    key={room.id}
                    className="bg-white rounded-2xl border border-slate-200/90 shadow-xs p-4 flex flex-col min-h-[300px]"
                  >
                    <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                      <div className="flex items-center gap-2">
                        <DoorOpen className="w-4 h-4 text-indigo-600" />
                        <h4 className="font-bold text-slate-800 text-sm">{room.name}</h4>
                      </div>
                      <button
                        type="button"
                        onClick={() =>
                          onOpenBookingModal({ date: activeDay.date, roomId: room.id })
                        }
                        className="p-1 rounded-lg text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 transition"
                        title={`Book in ${room.name}`}
                      >
                        <Plus className="w-4 h-4" />
                      </button>
                    </div>

                    <div className="py-3 space-y-2.5 flex-1">
                      {roomSessions.length === 0 ? (
                        <div className="py-10 text-center text-xs text-slate-400 italic border border-dashed border-slate-200 rounded-xl">
                          No sessions scheduled
                        </div>
                      ) : (
                        roomSessions.map((session) => {
                          const theme = getSpecialtyTheme(session.specialist_name);
                          const isCancelled = session.status === 'cancelled';

                          return (
                            <div
                              key={session.id}
                              style={{
                                borderLeftWidth: '3px',
                                borderLeftColor: isCancelled ? '#cbd5e1' : theme.accentColor,
                              }}
                              className={`p-3 rounded-xl border space-y-1.5 ${
                                isCancelled
                                  ? 'bg-slate-50 border-slate-200 opacity-60'
                                  : 'bg-white border-slate-200 shadow-2xs'
                              }`}
                            >
                              <div className="flex items-center justify-between text-xs font-mono font-semibold text-slate-700">
                                <span className="inline-flex items-center gap-1">
                                  <Clock className="w-3 h-3 text-slate-400" />
                                  {session.start_time}–{session.end_time}
                                </span>
                                <span className="uppercase text-[10px] font-sans px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                                  {session.status}
                                </span>
                              </div>
                              <div className="text-sm font-semibold text-slate-900">
                                {session.client_display_name}
                              </div>
                              <div className="text-xs text-slate-500">{session.specialist_name}</div>
                            </div>
                          );
                        })
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )
      )}
    </div>
  );
};
