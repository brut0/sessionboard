import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DayBoard } from './DayBoard';
import { server } from '../test/mocks/server';
import { http, HttpResponse } from 'msw';

const BASE = 'http://localhost:8000';

describe('DayBoard Component', () => {
  it('renders room columns and sessions grouped by room (AC-3.1)', async () => {
    const onDateChange = vi.fn();
    const onOpenBooking = vi.fn();

    render(
      <DayBoard
        selectedDate="2026-11-20"
        onDateChange={onDateChange}
        onOpenBookingModal={onOpenBooking}
      />
    );

    // Verify rooms appear
    expect(await screen.findByText('Room A')).toBeInTheDocument();
    expect(screen.getByText('Room B')).toBeInTheDocument();
    expect(screen.getByText('Room C')).toBeInTheDocument();

    // Verify session in Room A
    expect(screen.getByTestId('session-card-101')).toBeInTheDocument();
    expect(screen.getByTestId('session-card-101')).toHaveTextContent('Alex Morgan');
    expect(screen.getByText('Client 01')).toBeInTheDocument();
    expect(screen.getByText('10:00–11:00')).toBeInTheDocument();
    expect(screen.getByTestId('session-status-101')).toHaveTextContent('planned');

    // Rooms B and C are empty
    expect(screen.getAllByText('No sessions scheduled')).toHaveLength(2);
  });

  it('clicking Done transitions status from planned to done (AC-4.1)', async () => {
    render(
      <DayBoard
        selectedDate="2026-11-20"
        onDateChange={vi.fn()}
        onOpenBookingModal={vi.fn()}
      />
    );

    expect(await screen.findByTestId('session-card-101')).toBeInTheDocument();
    const btnDone = screen.getByTestId('btn-done-101');
    fireEvent.click(btnDone);

    await waitFor(() => {
      expect(screen.getByTestId('session-status-101')).toHaveTextContent('done');
    });
    // Buttons are gone when done
    expect(screen.queryByTestId('btn-done-101')).not.toBeInTheDocument();
  });

  it('clicking Cancel transitions status to cancelled and greys out card (AC-4.1, AC-4.2)', async () => {
    render(
      <DayBoard
        selectedDate="2026-11-20"
        onDateChange={vi.fn()}
        onOpenBookingModal={vi.fn()}
      />
    );

    expect(await screen.findByTestId('session-card-101')).toBeInTheDocument();
    const btnCancel = screen.getByTestId('btn-cancel-101');
    fireEvent.click(btnCancel);

    await waitFor(() => {
      expect(screen.getByTestId('session-status-101')).toHaveTextContent('cancelled');
    });
    const card = screen.getByTestId('session-card-101');
    expect(card.className).toContain('opacity-60');
  });

  it('handles date navigation controls correctly', async () => {
    const onDateChange = vi.fn();
    render(
      <DayBoard
        selectedDate="2026-11-20"
        onDateChange={onDateChange}
        onOpenBookingModal={vi.fn()}
      />
    );

    await screen.findByText('Room A');

    fireEvent.click(screen.getByTestId('btn-prev-day'));
    expect(onDateChange).toHaveBeenCalledWith('2026-11-19');

    fireEvent.click(screen.getByTestId('btn-next-day'));
    expect(onDateChange).toHaveBeenCalledWith('2026-11-21');

    fireEvent.change(screen.getByTestId('date-picker'), { target: { value: '2026-12-01' } });
    expect(onDateChange).toHaveBeenCalledWith('2026-12-01');
  });

  it('displays action error when status update fails', async () => {
    server.use(
      http.patch(`${BASE}/api/sessions/:session_id`, () => {
        return HttpResponse.json(
          { detail: 'session_already_cancelled' },
          { status: 409, headers: { 'x-trace-id': 'test-trace-999' } }
        );
      })
    );

    render(
      <DayBoard
        selectedDate="2026-11-20"
        onDateChange={vi.fn()}
        onOpenBookingModal={vi.fn()}
      />
    );

    expect(await screen.findByTestId('session-card-101')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('btn-done-101'));

    expect(await screen.findByTestId('action-error-banner')).toBeInTheDocument();
    expect(screen.getByText(/session_already_cancelled \(Trace ID: test-trace-999\)/)).toBeInTheDocument();
  });

  it('renders KPI ribbon and dims non-matching specialist cards when filtering', async () => {
    server.use(
      http.get(`${BASE}/api/sessions`, () => {
        return HttpResponse.json([
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
            status: 'planned',
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
          },
          {
            id: 102,
            specialist_id: 2,
            specialist_name: 'Sam Lee',
            client_id: 2,
            client_display_name: 'Client 02',
            room_id: 2,
            room_name: 'Room B',
            session_date: '2026-11-20',
            start_time: '12:00',
            end_time: '13:00',
            duration_minutes: 60,
            status: 'done',
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
          },
        ]);
      })
    );

    render(
      <DayBoard
        selectedDate="2026-11-20"
        onDateChange={vi.fn()}
        onOpenBookingModal={vi.fn()}
      />
    );

    expect(await screen.findByTestId('kpi-ribbon')).toBeInTheDocument();
    expect(screen.getByTestId('kpi-total')).toHaveTextContent('2');
    expect(screen.getByTestId('kpi-planned')).toHaveTextContent('1');
    expect(screen.getByTestId('kpi-done')).toHaveTextContent('1');

    const filterBar = screen.getByTestId('specialist-filter-bar');
    expect(filterBar).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('filter-specialist-1'));
    expect(screen.getByTestId('session-card-102').className).toContain('opacity-30');
    expect(screen.getByTestId('session-card-101').className).not.toContain('opacity-30');
  });

  it('switches to Gantt Timeline, toggles By Specialist, and opens booking prefill on empty slot click', async () => {
    const onOpenBooking = vi.fn();
    render(
      <DayBoard
        selectedDate="2026-11-20"
        onDateChange={vi.fn()}
        onOpenBookingModal={onOpenBooking}
      />
    );

    await screen.findByText('Room A');

    fireEvent.click(screen.getByTestId('view-mode-gantt'));
    expect(screen.getByTestId('gantt-timeline-view')).toBeInTheDocument();
    expect(screen.getByTestId('gantt-session-101')).toBeInTheDocument();

    // Click an empty slot in Room B at 14:00
    fireEvent.click(screen.getByTestId('gantt-slot-2-14:00'));
    expect(onOpenBooking).toHaveBeenCalledWith(
      expect.objectContaining({
        roomId: 2,
        startTime: '14:00',
        date: '2026-11-20',
      })
    );

    // Toggle By Specialist grouping
    fireEvent.click(screen.getByTestId('gantt-group-specialist'));
    fireEvent.click(screen.getByTestId('gantt-slot-1-15:00'));
    expect(onOpenBooking).toHaveBeenCalledWith(
      expect.objectContaining({
        specialistId: 1,
        startTime: '15:00',
        date: '2026-11-20',
      })
    );
  });

  it('opens slide-over session drawer when clicking a session card', async () => {
    const onOpenBooking = vi.fn();
    render(
      <DayBoard
        selectedDate="2026-11-20"
        onDateChange={vi.fn()}
        onOpenBookingModal={onOpenBooking}
      />
    );

    const card = await screen.findByTestId('session-card-101');
    fireEvent.click(card);

    const drawer = screen.getByTestId('session-drawer');
    expect(drawer).toBeInTheDocument();
    expect(drawer).toHaveTextContent('Alex Morgan');
    expect(drawer).toHaveTextContent('Client 01');
    expect(drawer).toHaveTextContent('Room A');

    fireEvent.click(screen.getByTestId('btn-book-followup'));
    expect(onOpenBooking).toHaveBeenCalledWith(
      expect.objectContaining({
        specialistId: 1,
        clientId: 1,
        roomId: 1,
        date: '2026-11-20',
      })
    );
  });
});
