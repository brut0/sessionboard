import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import App from './App';

describe('App component', () => {
  it('renders Day Board tab by default and switches to Directory', () => {
    render(<App />);

    expect(screen.getByText('SessionBoard')).toBeInTheDocument();
    expect(screen.getByTestId('tab-board')).toBeInTheDocument();
    expect(screen.getByTestId('tab-directory')).toBeInTheDocument();

    // Default Day Board elements
    expect(screen.getByTestId('btn-new-session')).toBeInTheDocument();
    expect(screen.getByText('Room A')).toBeInTheDocument();

    // Switch to Directory
    fireEvent.click(screen.getByTestId('tab-directory'));
    expect(screen.getByText('Specialists')).toBeInTheDocument();
    expect(screen.getByText('Clients')).toBeInTheDocument();
  });
});
