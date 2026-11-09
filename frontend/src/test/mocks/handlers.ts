import { http, HttpResponse } from 'msw';

const BASE = 'http://localhost:8000';

export const mockRooms = [
  { id: 1, name: 'Room A', created_at: '2026-01-01T00:00:00Z' },
  { id: 2, name: 'Room B', created_at: '2026-01-01T00:00:00Z' },
  { id: 3, name: 'Room C', created_at: '2026-01-01T00:00:00Z' },
];

export const mockSpecialists = [
  { id: 1, name: 'Alex Morgan', specialty: 'Math tutor', created_at: '2026-01-01T00:00:00Z' },
  { id: 2, name: 'Sam Lee', specialty: 'Guitar coach', created_at: '2026-01-01T00:00:00Z' },
];

export const mockClients = [
  { id: 1, display_name: 'Client 01', created_at: '2026-01-01T00:00:00Z' },
  { id: 2, display_name: 'Client 02', created_at: '2026-01-01T00:00:00Z' },
];

export const mockSessions = [
  {
    id: 101,
    specialist_id: 1,
    specialist_name: 'Alex Morgan',
    client_id: 1,
    client_display_name: 'Client 01',
    room_id: 1,
    room_name: 'Room A',
    session_date: '2026-11-20',
    start_time: '10:00',
    end_time: '11:00',
    duration_minutes: 60,
    status: 'planned' as const,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

export const handlers = [
  http.get(`${BASE}/api/rooms`, () => HttpResponse.json(mockRooms)),
  http.get(`${BASE}/api/specialists`, () => HttpResponse.json(mockSpecialists)),
  http.get(`${BASE}/api/clients`, () => HttpResponse.json(mockClients)),
  http.get(`${BASE}/api/sessions`, () => HttpResponse.json(mockSessions)),
  http.patch(`${BASE}/api/sessions/:session_id`, async ({ params, request }) => {
    const { session_id } = params;
    const body = (await request.json()) as { status: 'done' | 'cancelled' };
    return HttpResponse.json({
      id: Number(session_id),
      specialist_id: 1,
      specialist_name: 'Alex Morgan',
      client_id: 1,
      client_display_name: 'Client 01',
      room_id: 1,
      room_name: 'Room A',
      session_date: '2026-11-20',
      start_time: '10:00',
      end_time: '11:00',
      duration_minutes: 60,
      status: body.status,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    });
  }),
];
