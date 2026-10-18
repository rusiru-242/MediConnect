import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ToastProvider, useToast } from '../context/ToastContext';

const TestComponent: React.FC = () => {
  const { showToast, dismissToast } = useToast();

  return (
    <div>
      <button
        onClick={() =>
          showToast('Record updated successfully.', 'success', 3000)
        }
      >
        Trigger Success Toast
      </button>
      <button
        onClick={() =>
          showToast('Could not connect to database.', 'error', 0)
        }
      >
        Trigger Error Toast
      </button>
      <button onClick={() => dismissToast('custom-id')}>Dismiss Custom Toast</button>
    </div>
  );
};

describe('Toast Notification System', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders children within ToastProvider', () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>
    );

    expect(screen.getByText('Trigger Success Toast')).toBeInTheDocument();
  });

  it('displays a success notification when triggered', () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>
    );

    fireEvent.click(screen.getByText('Trigger Success Toast'));

    expect(screen.getByText('Record updated successfully.')).toBeInTheDocument();
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('displays an error notification with alert role when triggered', () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>
    );

    fireEvent.click(screen.getByText('Trigger Error Toast'));

    expect(screen.getByText('Could not connect to database.')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('dismisses toast on close button click', () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>
    );

    fireEvent.click(screen.getByText('Trigger Success Toast'));
    expect(screen.getByText('Record updated successfully.')).toBeInTheDocument();

    const closeBtn = screen.getByRole('button', { name: /Dismiss notification/i });
    fireEvent.click(closeBtn);

    expect(screen.queryByText('Record updated successfully.')).not.toBeInTheDocument();
  });

  it('automatically auto-dismisses toast after specified duration', () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>
    );

    fireEvent.click(screen.getByText('Trigger Success Toast'));
    expect(screen.getByText('Record updated successfully.')).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(3100);
    });

    expect(screen.queryByText('Record updated successfully.')).not.toBeInTheDocument();
  });
});
