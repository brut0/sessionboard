import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import App from './App';

describe('App component', () => {
  it('renders Left Sidebar navigation and switches between Day Board, Week Overview, and Directory', async () => {
    render(<App />);

    expect(screen.getByText('SessionBoard')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-nav')).toBeInTheDocument();
    expect(screen.getByTestId('tab-board')).toBeInTheDocument();
    expect(screen.getByTestId('tab-week')).toBeInTheDocument();
    expect(screen.getByTestId('tab-directory')).toBeInTheDocument();

    // Default Day Board elements
    expect(screen.getByTestId('btn-new-session')).toBeInTheDocument();
    expect(await screen.findByText('Room A')).toBeInTheDocument();

    // Switch to Week Overview
    fireEvent.click(screen.getByTestId('tab-week'));
    expect(await screen.findByTestId('week-board')).toBeInTheDocument();

    // Switch to Directory
    fireEvent.click(screen.getByTestId('tab-directory'));
    expect(await screen.findByTestId('directory-page')).toBeInTheDocument();
    expect(await screen.findByText('Specialists')).toBeInTheDocument();
    expect(screen.getByText('Clients')).toBeInTheDocument();
  });
});
