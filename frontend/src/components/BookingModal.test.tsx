import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BookingModal } from './BookingModal';
import { server } from '../test/mocks/server';
import { http, HttpResponse } from 'msw';

const BASE = 'http://localhost:8000';

describe('BookingModal Component', () => {
  it('submits valid booking, closes modal, and calls onSuccess (AC-2.1)', async () => {
    let capturedBody: unknown = null;
    server.use(
      http.post(`${BASE}/api/sessions`, async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json(
          {
            id: 201,
            specialist_id: 1,
            specialist_name: 'Alex Morgan',
            client_id: 1,
            client_display_name: 'Client 01',
            room_id: 1,
            room_name: 'Room A',
            session_date: '2026-11-25',
            start_time: '09:00',
            end_time: '10:00',
            duration_minutes: 60,
            status: 'planned',
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
          },
          { status: 201 }
        );
      })
    );

    const onClose = vi.fn();
    const onSuccess = vi.fn();

    render(
      <BookingModal
        isOpen={true}
        onClose={onClose}
        onSuccess={onSuccess}
        initialDate="2026-11-25"
      />
    );

    // Wait for dropdowns to populate from directory endpoints
    await waitFor(() => {
      expect(screen.getByText('Alex Morgan (Math tutor)')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('btn-submit-booking'));

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalled();
      expect(onClose).toHaveBeenCalled();
    });

    expect(capturedBody).toEqual({
      session_date: '2026-11-25',
      start_time: '09:00',
      duration_minutes: 60,
      specialist_id: 1,
      room_id: 1,
      client_id: 1,
    });
  });

  it('renders conflict list on HTTP 409 Conflict (AC-2.5, AC-2.6)', async () => {
    server.use(
      http.post(`${BASE}/api/sessions`, () => {
        return HttpResponse.json(
          {
            detail: 'conflict',
            conflicts: [
              { type: 'specialist', session_id: 12 },
              { type: 'room', session_id: 12 },
              { type: 'client', session_id: 15 },
            ],
          },
          { status: 409 }
        );
      })
    );

    render(
      <BookingModal
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
        initialDate="2026-11-25"
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Alex Morgan (Math tutor)')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('btn-submit-booking'));

    expect(await screen.findByTestId('conflict-banner')).toBeInTheDocument();
    expect(screen.getByText('Specialist is busy (session #12)')).toBeInTheDocument();
    expect(screen.getByText('Room is busy (session #12)')).toBeInTheDocument();
    expect(screen.getByText('Client is busy (session #15)')).toBeInTheDocument();
  });

  it('renders Trace ID error banner on HTTP 500 error', async () => {
    server.use(
      http.post(`${BASE}/api/sessions`, () => {
        return HttpResponse.json(
          { detail: 'internal_error' },
          {
            status: 500,
            headers: {
              'x-trace-id': '4f506a56979ae0285bc8171c4fc33112',
            },
          }
        );
      })
    );

    render(
      <BookingModal
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
        initialDate="2026-11-25"
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Alex Morgan (Math tutor)')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('btn-submit-booking'));

    expect(await screen.findByTestId('booking-error-banner')).toBeInTheDocument();
    expect(
      screen.getByText('Something went wrong. Trace ID: 4f506a56979ae0285bc8171c4fc33112')
    ).toBeInTheDocument();
  });

  it('closes modal when close button is clicked', () => {
    const onClose = vi.fn();
    render(
      <BookingModal
        isOpen={true}
        onClose={onClose}
        onSuccess={vi.fn()}
        initialDate="2026-11-25"
      />
    );

    fireEvent.click(screen.getByTestId('btn-close-modal'));
    expect(onClose).toHaveBeenCalled();
  });
});
