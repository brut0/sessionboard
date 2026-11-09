import React, { useEffect, useState, useCallback } from 'react';
import { Calendar, Plus, Clock, User, CheckCircle2, XCircle, AlertCircle } from 'lucide-react';
import { apiClient, type Room, type Session } from '../api/client';

interface DayBoardProps {
  selectedDate: string;
  onDateChange: (date: string) => void;
  onOpenBookingModal: () => void;
  refreshTrigger?: number;
}

export const DayBoard: React.FC<DayBoardProps> = ({
  selectedDate,
  onDateChange,
  onOpenBookingModal,
  refreshTrigger = 0,
}) => {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const fetchBoardData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [roomsRes, sessionsRes] = await Promise.all([
        apiClient.GET('/api/rooms'),
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
    const d = new Date(selectedDate);
    d.setDate(d.getDate() - 1);
    onDateChange(d.toISOString().split('T')[0]);
  };

  const handleNextDay = () => {
    const d = new Date(selectedDate);
    d.setDate(d.getDate() + 1);
    onDateChange(d.toISOString().split('T')[0]);
  };

  const handleToday = () => {
    onDateChange(new Date().toISOString().split('T')[0]);
  };

  const handleStatusUpdate = async (sessionId: number, targetStatus: 'done' | 'cancelled') => {
    setActionError(null);
    try {
      const { data, error: patchErr, response } = await apiClient.PATCH('/api/sessions/{session_id}', {
        params: { path: { session_id: sessionId } },
        body: { status: targetStatus },
      });

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

  return (
    <div className="space-y-6">
      {/* Board Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
        <div className="flex items-center gap-2">
          <button
            type="button"
            data-testid="btn-prev-day"
            onClick={handlePrevDay}
            className="px-3 py-1.5 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition"
          >
            ◀ Prev
          </button>
          <button
            type="button"
            data-testid="btn-today"
            onClick={handleToday}
            className="px-3 py-1.5 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition"
          >
            Today
          </button>
          <button
            type="button"
            data-testid="btn-next-day"
            onClick={handleNextDay}
            className="px-3 py-1.5 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition"
          >
            Next ▶
          </button>
          <div className="flex items-center gap-2 ml-2 pl-3 border-l border-slate-200">
            <Calendar className="w-4 h-4 text-slate-400" />
            <input
              type="date"
              data-testid="date-picker"
              value={selectedDate}
              onChange={(e) => onDateChange(e.target.value)}
              className="border border-slate-300 rounded-md px-2.5 py-1 text-sm text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>

        <button
          type="button"
          data-testid="btn-new-session"
          onClick={onOpenBookingModal}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm font-medium shadow-xs transition"
        >
          <Plus className="w-4 h-4" />
          New Session
        </button>
      </div>

      {actionError && (
        <div
          data-testid="action-error-banner"
          className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm flex items-center gap-2"
        >
          <AlertCircle className="w-4 h-4 shrink-0 text-red-500" />
          <span>{actionError}</span>
        </div>
      )}

      {error && (
        <div
          data-testid="fetch-error-banner"
          className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm flex items-center gap-2"
        >
          <AlertCircle className="w-5 h-5 shrink-0 text-red-500" />
          <span>{error}</span>
        </div>
      )}

      {/* Room Columns Grid */}
      {loading ? (
        <div className="text-center py-12 text-slate-400 text-sm">Loading day schedule...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {rooms.map((room) => {
            const roomSessions = sessions.filter((s) => s.room_id === room.id);
            return (
              <div
                key={room.id}
                data-testid={`room-column-${room.id}`}
                className="bg-white rounded-xl border border-slate-200 shadow-xs p-4 flex flex-col"
              >
                <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                  <h2 className="font-semibold text-slate-800 text-base">{room.name}</h2>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-medium">
                    {roomSessions.length} {roomSessions.length === 1 ? 'session' : 'sessions'}
                  </span>
                </div>

                <div className="py-4 space-y-3 flex-1">
                  {roomSessions.length === 0 ? (
                    <div className="py-12 text-center text-sm text-slate-400 italic">
                      No sessions scheduled
                    </div>
                  ) : (
                    roomSessions.map((session) => {
                      const isPlanned = session.status === 'planned';
                      const isDone = session.status === 'done';
                      const isCancelled = session.status === 'cancelled';

                      return (
                        <div
                          key={session.id}
                          data-testid={`session-card-${session.id}`}
                          className={`p-3.5 rounded-lg border transition ${
                            isCancelled
                              ? 'bg-slate-50 border-slate-200 opacity-60 text-slate-500'
                              : isDone
                              ? 'bg-emerald-50/40 border-emerald-200 shadow-2xs'
                              : 'bg-white border-slate-200 shadow-xs hover:border-indigo-300'
                          }`}
                        >
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
                              <Clock className="w-3.5 h-3.5 text-slate-400" />
                              <span>
                                {session.start_time}–{session.end_time}
                              </span>
                              <span className="text-slate-400 font-normal">
                                ({session.duration_minutes}m)
                              </span>
                            </div>
                            <span
                              data-testid={`session-status-${session.id}`}
                              className={`text-[11px] font-medium px-2 py-0.5 rounded-full uppercase tracking-wider ${
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

                          <div className="space-y-1 text-sm">
                            <div className="font-medium text-slate-900 flex items-center gap-1.5">
                              <User className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                              <span className={isCancelled ? 'line-through' : ''}>
                                {session.specialist_name}
                              </span>
                            </div>
                            <div className="text-xs text-slate-500 pl-5">
                              Client: <span className="text-slate-700 font-medium">{session.client_display_name}</span>
                            </div>
                          </div>

                          {isPlanned && (
                            <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center gap-2">
                              <button
                                type="button"
                                data-testid={`btn-done-${session.id}`}
                                onClick={() => handleStatusUpdate(session.id, 'done')}
                                className="flex-1 flex items-center justify-center gap-1 px-2.5 py-1 text-xs font-medium text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded-md transition"
                              >
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                Done
                              </button>
                              <button
                                type="button"
                                data-testid={`btn-cancel-${session.id}`}
                                onClick={() => handleStatusUpdate(session.id, 'cancelled')}
                                className="flex-1 flex items-center justify-center gap-1 px-2.5 py-1 text-xs font-medium text-slate-600 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-md transition"
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
      )}
    </div>
  );
};
