import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { WeekBoard } from './WeekBoard';
import { server } from '../test/mocks/server';
import { http, HttpResponse } from 'msw';

const BASE = 'http://localhost:8000';

describe('WeekBoard Component', () => {
  it('loads 7-day week matrix, displays day pill counts, and switches to single-day room grid', async () => {
    // 2026-11-20 is Friday; ISO week is 2026-11-16 (Mon) .. 2026-11-22 (Sun)
    server.use(
      http.get(`${BASE}/api/sessions`, ({ request }) => {
        const url = new URL(request.url);
        const date = url.searchParams.get('date');
        if (date === '2026-11-16') {
          return HttpResponse.json([
            {
              id: 201,
              specialist_id: 1,
              specialist_name: 'Alex Morgan',
              client_id: 1,
              client_display_name: 'Client 01',
              room_id: 1,
              room_name: 'Room A',
              session_date: '2026-11-16',
              start_time: '09:00',
              end_time: '10:00',
              duration_minutes: 60,
              status: 'planned',
              created_at: '2026-01-01T00:00:00Z',
              updated_at: '2026-01-01T00:00:00Z',
            },
          ]);
        }
        if (date === '2026-11-20') {
          return HttpResponse.json([
            {
              id: 202,
              specialist_id: 2,
              specialist_name: 'Sam Lee',
              client_id: 2,
              client_display_name: 'Client 02',
              room_id: 2,
              room_name: 'Room B',
              session_date: '2026-11-20',
              start_time: '14:00',
              end_time: '15:00',
              duration_minutes: 60,
              status: 'done',
              created_at: '2026-01-01T00:00:00Z',
              updated_at: '2026-01-01T00:00:00Z',
            },
          ]);
        }
        return HttpResponse.json([]);
      })
    );

    const onDateChange = vi.fn();
    const onSelectDayView = vi.fn();
    const onOpenBookingModal = vi.fn();

    render(
      <WeekBoard
        selectedDate="2026-11-20"
        onDateChange={onDateChange}
        onSelectDayView={onSelectDayView}
        onOpenBookingModal={onOpenBookingModal}
      />
    );

    expect(await screen.findByTestId('week-board')).toBeInTheDocument();
    expect(await screen.findByText('Client 01')).toBeInTheDocument();
    expect(screen.getByText('Client 02')).toBeInTheDocument();

    // Whole Week and 7 day pills exist with session counts
    expect(screen.getByTestId('week-filter-all')).toHaveTextContent('2');
    expect(screen.getByTestId('week-day-pill-0')).toHaveTextContent('Mon');
    expect(screen.getByTestId('week-day-pill-0')).toHaveTextContent('1');
    expect(screen.getByTestId('week-day-pill-4')).toHaveTextContent('Fri');
    expect(screen.getByTestId('week-day-pill-4')).toHaveTextContent('1');

    // Switch to Monday single-day room grid
    fireEvent.click(screen.getByTestId('week-day-pill-0'));
    await waitFor(() => {
      expect(screen.getByTestId('week-single-day-grid')).toBeInTheDocument();
    });
    expect(screen.getByText('Room A')).toBeInTheDocument();
    expect(screen.getByText('Client 01')).toBeInTheDocument();

    // Switch back to Whole Week
    fireEvent.click(screen.getByTestId('week-filter-all'));
    expect(screen.getByTestId('week-matrix-grid')).toBeInTheDocument();
  });

  it('navigates between weeks with Prev Week and Next Week buttons', async () => {
    const onDateChange = vi.fn();
    render(
      <WeekBoard
        selectedDate="2026-11-20"
        onDateChange={onDateChange}
        onSelectDayView={vi.fn()}
        onOpenBookingModal={vi.fn()}
      />
    );

    await screen.findByTestId('week-matrix-grid');

    fireEvent.click(screen.getByTestId('btn-prev-week'));
    expect(onDateChange).toHaveBeenCalledWith('2026-11-13');

    fireEvent.click(screen.getByTestId('btn-next-week'));
    expect(onDateChange).toHaveBeenCalledWith('2026-11-27');
  });
});
