import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DirectoryPage } from './DirectoryPage';
import { server } from '../test/mocks/server';
import { http, HttpResponse } from 'msw';

const BASE = 'http://localhost:8000';

describe('DirectoryPage Component', () => {
  it('renders specialists, clients, and rooms from directory API (AC-1.1)', async () => {
    render(<DirectoryPage />);

    expect(await screen.findByText('Alex Morgan')).toBeInTheDocument();
    expect(screen.getByText('Math tutor')).toBeInTheDocument();
    expect(screen.getByText('Client 01')).toBeInTheDocument();
    expect(screen.getByText('Room A')).toBeInTheDocument();
  });

  it('creates new specialist, client, and room (AC-1.1)', async () => {
    server.use(
      http.post(`${BASE}/api/specialists`, async ({ request }) => {
        const body = (await request.json()) as { name: string; specialty: string };
        return HttpResponse.json({ id: 99, name: body.name, specialty: body.specialty, created_at: '' }, { status: 201 });
      }),
      http.post(`${BASE}/api/clients`, async ({ request }) => {
        const body = (await request.json()) as { display_name: string };
        return HttpResponse.json({ id: 99, display_name: body.display_name, created_at: '' }, { status: 201 });
      }),
      http.post(`${BASE}/api/rooms`, async ({ request }) => {
        const body = (await request.json()) as { name: string };
        return HttpResponse.json({ id: 99, name: body.name, created_at: '' }, { status: 201 });
      })
    );

    render(<DirectoryPage />);

    await screen.findByText('Alex Morgan');

    // Add specialist
    fireEvent.change(screen.getByTestId('input-specialist-name'), { target: { value: 'New Spec' } });
    fireEvent.change(screen.getByTestId('input-specialist-specialty'), { target: { value: 'Physics' } });
    fireEvent.click(screen.getByTestId('btn-add-specialist'));
    expect(await screen.findByText('New Spec')).toBeInTheDocument();

    // Add client
    fireEvent.change(screen.getByTestId('input-client-name'), { target: { value: 'Client 99' } });
    fireEvent.click(screen.getByTestId('btn-add-client'));
    expect(await screen.findByText('Client 99')).toBeInTheDocument();

    // Add room
    fireEvent.change(screen.getByTestId('input-room-name'), { target: { value: 'Room D' } });
    fireEvent.click(screen.getByTestId('btn-add-room'));
    expect(await screen.findByText('Room D')).toBeInTheDocument();
  });

  it('displays "Room name already exists" when room name is duplicated (AC-1.3)', async () => {
    server.use(
      http.post(`${BASE}/api/rooms`, () => {
        return HttpResponse.json({ detail: 'room_name_taken' }, { status: 409 });
      })
    );

    render(<DirectoryPage />);
    await screen.findByText('Room A');

    fireEvent.change(screen.getByTestId('input-room-name'), { target: { value: 'Room A' } });
    fireEvent.click(screen.getByTestId('btn-add-room'));

    expect(await screen.findByTestId('directory-error-banner')).toBeInTheDocument();
    expect(screen.getByText('Room name already exists')).toBeInTheDocument();
  });

  it('displays "Cannot delete: has planned sessions" when delete returns 409 (AC-1.5)', async () => {
    server.use(
      http.delete(`${BASE}/api/rooms/:room_id`, () => {
        return HttpResponse.json({ detail: 'has_planned_sessions' }, { status: 409 });
      })
    );

    render(<DirectoryPage />);
    await screen.findByText('Room A');

    fireEvent.click(screen.getByTestId('btn-delete-room-1'));

    expect(await screen.findByTestId('directory-error-banner')).toBeInTheDocument();
    expect(screen.getByText('Cannot delete: has planned sessions')).toBeInTheDocument();
  });

  it('deletes unused room successfully on 204 (AC-1.4)', async () => {
    server.use(
      http.delete(`${BASE}/api/rooms/:room_id`, () => {
        return new HttpResponse(null, { status: 204 });
      })
    );

    render(<DirectoryPage />);
    await screen.findByText('Room A');

    fireEvent.click(screen.getByTestId('btn-delete-room-1'));

    await waitFor(() => {
      expect(screen.queryByText('Room A')).not.toBeInTheDocument();
    });
  });
});
