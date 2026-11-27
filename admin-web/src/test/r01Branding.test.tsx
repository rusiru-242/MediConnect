// R01 branding: the MediConnect symbol replaces the generic shield beside the existing title, is decorative (the name
// is already text), keeps its proportions, and index.html declares real favicons instead of the missing /vite.svg.
import fs from 'node:fs';
import path from 'node:path';
import { render, screen, within } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { LoginPage } from '../pages/LoginPage';
import { Sidebar } from '../components/layout/Sidebar';
import { AuthProvider } from '../context/AuthContext';

vi.mock('../api/authApi', () => ({
  authApi: { login: vi.fn(), getCurrentUser: vi.fn(), checkHealth: vi.fn() },
}));

const ROOT = path.resolve(__dirname, '..', '..');

function expectBrandMark(container: HTMLElement) {
  const marks = within(container).getAllByTestId('brand-mark');
  expect(marks).toHaveLength(1);
  const img = marks[0] as HTMLImageElement;
  expect(img.getAttribute('src')).toMatch(/mediconnect-symbol\.png/);
  expect(img).toHaveAttribute('alt', '');
  expect(img).toHaveAttribute('aria-hidden', 'true');
  expect(img.className).toContain('object-contain');
}

describe('R01 admin branding', () => {
  it('login page shows one brand symbol above the existing title', () => {
    const { container } = render(
      <AuthProvider>
        <MemoryRouter>
          <LoginPage />
        </MemoryRouter>
      </AuthProvider>
    );
    expectBrandMark(container);
    expect(screen.getByText('MediConnect Admin')).toBeInTheDocument();
    // No duplicated wordmark: the name appears once as text and the symbol image carries no text.
    expect(screen.getAllByText(/MediConnect/)).toHaveLength(1);
  });

  it('sidebar brand area shows the symbol beside the MediConnect title and keeps navigation', () => {
    const { container } = render(
      <MemoryRouter>
        <Sidebar isOpen onClose={() => {}} />
      </MemoryRouter>
    );
    const aside = container.querySelector('aside') as HTMLElement;
    expectBrandMark(aside);
    expect(within(aside).getByText('MediConnect')).toBeInTheDocument();
    expect(within(aside).getByRole('link', { name: /Dashboard/ })).toBeInTheDocument();
    expect(within(aside).getByRole('button', { name: /Close sidebar/ })).toBeInTheDocument();
  });

  it('index.html declares existing favicon files and keeps the document title', () => {
    const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
    expect(html).not.toContain('/vite.svg');
    expect(html).toContain('<title>MediConnect — Administration Portal</title>');
    const hrefs = [...html.matchAll(/<link rel="(?:icon|apple-touch-icon)"[^>]*href="\/([^"]+)"/g)].map((m) => m[1]);
    expect(hrefs).toEqual(['favicon.ico', 'favicon-32x32.png', 'favicon-16x16.png', 'apple-touch-icon.png']);
    for (const href of hrefs) {
      const file = path.join(ROOT, 'public', href);
      expect(fs.existsSync(file), href).toBe(true);
      expect(fs.statSync(file).size).toBeGreaterThan(300);
    }
  });
});
