import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DayBoard } from './DayBoard';
import { server } from '../test/mocks/server';
import { http, HttpResponse } from 'msw';

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
    expect(screen.getByText('Alex Morgan')).toBeInTheDocument();
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
      http.patch('http://localhost:8000/api/sessions/:session_id', () => {
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
});
