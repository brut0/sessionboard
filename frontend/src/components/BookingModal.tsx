import React, { useState, useEffect } from 'react';
import { X, Calendar, Clock, AlertTriangle, AlertCircle } from 'lucide-react';
import {
  apiClient,
  type Specialist,
  type Client,
  type Room,
  type ConflictItem,
  type ConflictError,
} from '../api/client';

interface BookingModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  initialDate: string;
  initialRoomId?: number;
  initialSpecialistId?: number;
  initialClientId?: number;
  initialStartTime?: string;
}

const START_TIMES: string[] = [];
for (let h = 8; h <= 19; h++) {
  for (let m = 0; m < 60; m += 15) {
    const hh = String(h).padStart(2, '0');
    const mm = String(m).padStart(2, '0');
    START_TIMES.push(`${hh}:${mm}`);
  }
}

const DURATIONS = [15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165, 180];

export const BookingModal: React.FC<BookingModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  initialDate,
  initialRoomId,
  initialSpecialistId,
  initialClientId,
  initialStartTime,
}) => {
  const [specialists, setSpecialists] = useState<Specialist[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);

  const [specialistId, setSpecialistId] = useState<number | ''>('');
  const [clientId, setClientId] = useState<number | ''>('');
  const [roomId, setRoomId] = useState<number | ''>('');
  const [sessionDate, setSessionDate] = useState(initialDate);
  const [startTime, setStartTime] = useState('09:00');
  const [durationMinutes, setDurationMinutes] = useState(60);

  const [conflicts, setConflicts] = useState<ConflictItem[] | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setSessionDate(initialDate);
      setStartTime(initialStartTime && START_TIMES.includes(initialStartTime) ? initialStartTime : '09:00');
      setConflicts(null);
      setErrorMessage(null);

      // Fetch directory entities
      Promise.all([
        apiClient.GET('/api/specialists'),
        apiClient.GET('/api/clients'),
        apiClient.GET('/api/rooms'),
      ]).then(([specRes, clientRes, roomRes]) => {
        if (specRes.data && specRes.data.length > 0) {
          setSpecialists(specRes.data);
          const matchedSpec = initialSpecialistId
            ? specRes.data.find((s) => s.id === initialSpecialistId)
            : undefined;
          setSpecialistId(matchedSpec ? matchedSpec.id : specRes.data[0].id);
        }
        if (clientRes.data && clientRes.data.length > 0) {
          setClients(clientRes.data);
          const matchedClient = initialClientId
            ? clientRes.data.find((c) => c.id === initialClientId)
            : undefined;
          setClientId(matchedClient ? matchedClient.id : clientRes.data[0].id);
        }
        if (roomRes.data && roomRes.data.length > 0) {
          setRooms(roomRes.data);
          const matchedRoom = initialRoomId
            ? roomRes.data.find((r) => r.id === initialRoomId)
            : undefined;
          setRoomId(matchedRoom ? matchedRoom.id : roomRes.data[0].id);
        }
      });
    }
  }, [isOpen, initialDate, initialRoomId, initialSpecialistId, initialClientId, initialStartTime]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setConflicts(null);
    setErrorMessage(null);

    if (!specialistId || !clientId || !roomId) {
      setErrorMessage('Please select a specialist, client, and room');
      return;
    }

    setIsSubmitting(true);
    try {
      const { data, error, response } = await apiClient.POST('/api/sessions', {
        body: {
          session_date: sessionDate,
          start_time: startTime,
          duration_minutes: durationMinutes,
          specialist_id: Number(specialistId),
          room_id: Number(roomId),
          client_id: Number(clientId),
        },
      });

      if (response.status === 201 && data) {
        onSuccess();
        onClose();
        return;
      }

      if (response.status === 409 && error) {
        const conflictErr = error as ConflictError;
        setConflicts(conflictErr.conflicts || []);
        return;
      }

      if (response.status >= 500) {
        const traceId = response.headers.get('x-trace-id');
        setErrorMessage(
          traceId
            ? `Something went wrong. Trace ID: ${traceId}`
            : 'Something went wrong. Please try again.'
        );
        return;
      }

      // Handle 422 or other errors
      const detail = (error as { detail?: string | unknown[] })?.detail;
      if (typeof detail === 'string') {
        setErrorMessage(detail);
      } else {
        setErrorMessage('Validation error. Please verify session hours and duration.');
      }
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Network error submitting booking');
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatConflictMessage = (c: ConflictItem) => {
    const id = c.session_id ?? (c as unknown as { conflicting_session_id?: number }).conflicting_session_id;
    switch (c.type) {
      case 'specialist':
        return `Specialist is busy (session #${id})`;
      case 'room':
        return `Room is busy (session #${id})`;
      case 'client':
        return `Client is busy (session #${id})`;
      default:
        return `Conflict with session #${id}`;
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs"
    >
      <div
        data-testid="booking-modal"
        className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-150"
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div>
            <h2 id="modal-title" className="text-lg font-bold text-slate-900">
              New Session
            </h2>
            <p className="text-xs text-slate-500">Book a conflict-free studio session</p>
          </div>
          <button
            type="button"
            data-testid="btn-close-modal"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body / Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* General Error Banner (5xx or validation) */}
          {errorMessage && (
            <div
              data-testid="booking-error-banner"
              className="p-3.5 bg-red-50 border border-red-200 text-red-800 rounded-xl text-sm flex items-start gap-2.5"
            >
              <AlertCircle className="w-4 h-4 shrink-0 text-red-500 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* 409 Conflict Banner */}
          {conflicts && conflicts.length > 0 && (
            <div
              data-testid="conflict-banner"
              className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl text-sm space-y-1.5"
            >
              <div className="flex items-center gap-2 font-semibold text-amber-900">
                <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                <span>Scheduling conflict detected</span>
              </div>
              <ul data-testid="conflict-list" className="list-disc list-inside text-xs text-amber-800 space-y-0.5 pl-1">
                {conflicts.map((c, idx) => {
                  const id = c.session_id ?? (c as unknown as { conflicting_session_id?: number }).conflicting_session_id;
                  return (
                    <li key={`${c.type}-${id}-${idx}`} data-testid="conflict-item">
                      {formatConflictMessage(c)}
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {/* Specialist Select */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Specialist
            </label>
            <select
              data-testid="select-specialist"
              value={specialistId}
              onChange={(e) => setSpecialistId(e.target.value ? Number(e.target.value) : '')}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-800 bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
              required
            >
              <option value="" disabled>Select specialist</option>
              {specialists.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.specialty})
                </option>
              ))}
            </select>
          </div>

          {/* Client Select */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Client
            </label>
            <select
              data-testid="select-client"
              value={clientId}
              onChange={(e) => setClientId(e.target.value ? Number(e.target.value) : '')}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-800 bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
              required
            >
              <option value="" disabled>Select client</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.display_name}
                </option>
              ))}
            </select>
          </div>

          {/* Room Select */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Room
            </label>
            <select
              data-testid="select-room"
              value={roomId}
              onChange={(e) => setRoomId(e.target.value ? Number(e.target.value) : '')}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-800 bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
              required
            >
              <option value="" disabled>Select room</option>
              {rooms.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          </div>

          {/* Date Picker */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Date
            </label>
            <div className="relative">
              <input
                type="date"
                data-testid="input-session-date"
                value={sessionDate}
                onChange={(e) => setSessionDate(e.target.value)}
                className="w-full border border-slate-300 rounded-lg pl-9 pr-3 py-2 text-sm text-slate-800 bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                required
              />
              <Calendar className="w-4 h-4 text-slate-400 absolute left-3 top-2.5 pointer-events-none" />
            </div>
          </div>

          {/* Time & Duration Row */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Start Time
              </label>
              <div className="relative">
                <select
                  data-testid="select-start-time"
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg pl-9 pr-3 py-2 text-sm text-slate-800 bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                >
                  {START_TIMES.map((time) => (
                    <option key={time} value={time}>
                      {time}
                    </option>
                  ))}
                </select>
                <Clock className="w-4 h-4 text-slate-400 absolute left-3 top-2.5 pointer-events-none" />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Duration
              </label>
              <select
                data-testid="select-duration"
                value={durationMinutes}
                onChange={(e) => setDurationMinutes(Number(e.target.value))}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-800 bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
              >
                {DURATIONS.map((dur) => (
                  <option key={dur} value={dur}>
                    {dur} min ({dur / 60 >= 1 ? `${dur / 60}h` : ''}
                    {dur % 60 !== 0 ? `${dur % 60}m` : ''})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Modal Footer */}
          <div className="pt-4 border-t border-slate-100 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 rounded-lg transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              data-testid="btn-submit-booking"
              disabled={isSubmitting}
              className="px-5 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 rounded-lg shadow-xs transition"
            >
              {isSubmitting ? 'Booking...' : 'Book Session'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
