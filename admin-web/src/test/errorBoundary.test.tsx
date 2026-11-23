import React, { useState } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ErrorBoundary } from '../components/common/ErrorBoundary';

const FaultyComponent: React.FC<{ shouldThrow?: boolean }> = ({ shouldThrow }) => {
  if (shouldThrow) {
    throw new Error('Test crash in child component');
  }
  return <div>Component rendered safely.</div>;
};

describe('ErrorBoundary Component', () => {
  beforeEach(() => {
    // Silence error log during boundary test
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  it('renders children when no errors occur', () => {
    render(
      <ErrorBoundary>
        <FaultyComponent shouldThrow={false} />
      </ErrorBoundary>
    );

    expect(screen.getByText('Component rendered safely.')).toBeInTheDocument();
  });

  it('catches render errors and displays fallback UI', () => {
    render(
      <ErrorBoundary>
        <FaultyComponent shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText('An unexpected view error occurred')).toBeInTheDocument();
    expect(
      screen.getByText(/The administrative interface encountered an unhandled exception/i)
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Retry Module/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Back to Dashboard/i })).toBeInTheDocument();
  });

  it('renders custom fallback when provided', () => {
    render(
      <ErrorBoundary fallback={<div>Custom Error Placeholder</div>}>
        <FaultyComponent shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText('Custom Error Placeholder')).toBeInTheDocument();
    expect(screen.queryByText('An unexpected view error occurred')).not.toBeInTheDocument();
  });

  it('allows user to retry after resetting faulty state', () => {
    const ParentWrapper = () => {
      const [hasError, setHasError] = useState(true);
      return (
        <div>
          <button onClick={() => setHasError(false)}>Fix Error</button>
          <ErrorBoundary>
            <FaultyComponent shouldThrow={hasError} />
          </ErrorBoundary>
        </div>
      );
    };

    render(<ParentWrapper />);
    expect(screen.getByText('An unexpected view error occurred')).toBeInTheDocument();

    // Fix error in parent state
    fireEvent.click(screen.getByText('Fix Error'));

    // Click retry on error boundary
    const retryBtn = screen.getByRole('button', { name: /Retry Module/i });
    fireEvent.click(retryBtn);

    expect(screen.getByText('Component rendered safely.')).toBeInTheDocument();
  });
});
