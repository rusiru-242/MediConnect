import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { TopNav } from '../components/layout/TopNav';
import { AuthProvider } from '../context/AuthContext';

describe('Responsive Navigation & Accessibility', () => {
  it('renders Sidebar with accessible landmarks and navigation items', () => {
    const handleClose = vi.fn();
    render(
      <MemoryRouter>
        <Sidebar isOpen={true} onClose={handleClose} />
      </MemoryRouter>
    );

    const nav = screen.getByRole('navigation', { name: /Operations Menu/i });
    expect(nav).toBeInTheDocument();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Doctor Verification')).toBeInTheDocument();
    expect(screen.getByText('Appointments')).toBeInTheDocument();
  });

  it('triggers onClose when close button is clicked in mobile sidebar', () => {
    const handleClose = vi.fn();
    render(
      <MemoryRouter>
        <Sidebar isOpen={true} onClose={handleClose} />
      </MemoryRouter>
    );

    const closeBtn = screen.getByRole('button', { name: /Close sidebar/i });
    fireEvent.click(closeBtn);

    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('triggers onClose when Escape key is pressed while sidebar is open', () => {
    const handleClose = vi.fn();
    render(
      <MemoryRouter>
        <Sidebar isOpen={true} onClose={handleClose} />
      </MemoryRouter>
    );

    fireEvent.keyDown(window, { key: 'Escape', code: 'Escape' });

    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('renders TopNav hamburger button and invokes onOpenSidebar', () => {
    const handleOpen = vi.fn();
    render(
      <AuthProvider>
        <MemoryRouter>
          <TopNav onOpenSidebar={handleOpen} />
        </MemoryRouter>
      </AuthProvider>
    );

    const hamburgerBtn = screen.getByRole('button', { name: /Open navigation menu/i });
    expect(hamburgerBtn).toBeInTheDocument();

    fireEvent.click(hamburgerBtn);
    expect(handleOpen).toHaveBeenCalledTimes(1);
  });

  it('toggles user profile dropdown in TopNav with accessible state', () => {
    render(
      <AuthProvider>
        <MemoryRouter>
          <TopNav onOpenSidebar={vi.fn()} />
        </MemoryRouter>
      </AuthProvider>
    );

    const userMenuBtn = screen.getByRole('button', { name: /Administrator profile menu/i });
    expect(userMenuBtn).toHaveAttribute('aria-expanded', 'false');

    // Click to open
    fireEvent.click(userMenuBtn);
    expect(userMenuBtn).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('Sign Out')).toBeInTheDocument();

    // Press Escape to close dropdown
    fireEvent.keyDown(window, { key: 'Escape', code: 'Escape' });
    expect(userMenuBtn).toHaveAttribute('aria-expanded', 'false');
  });
});
