/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#2196f3', // Secondary Blue
          600: '#1565c0', // Primary Blue
          700: '#1976d2',
          800: '#0d47a1',
          900: '#172b4d', // Dark Navy
        },
        navy: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e5eaf2', // Border
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b', // Secondary Text
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#172b4d', // Dark Navy
          950: '#0f172a',
        },
        medical: {
          primary: '#1565C0',
          secondary: '#2196F3',
          navy: '#172B4D',
          bg: '#F5F8FC',
          surface: '#FFFFFF',
          border: '#E5EAF2',
          textSecondary: '#64748B',
          success: '#16A34A',
          warning: '#F59E0B',
          error: '#DC2626',
        },
      },
    },
  },
  plugins: [],
}
