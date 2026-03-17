/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // MARS token-backed colors
        mars: {
          primary: 'var(--mars-color-primary)',
          'primary-hover': 'var(--mars-color-primary-hover)',
          'primary-subtle': 'var(--mars-color-primary-subtle)',
          accent: 'var(--mars-color-accent)',
          'accent-hover': 'var(--mars-color-accent-hover)',
          surface: 'var(--mars-color-surface)',
          'surface-raised': 'var(--mars-color-surface-raised)',
          'surface-overlay': 'var(--mars-color-surface-overlay)',
          bg: 'var(--mars-color-bg)',
          'bg-secondary': 'var(--mars-color-bg-secondary)',
          'bg-hover': 'var(--mars-color-bg-hover)',
          text: 'var(--mars-color-text)',
          'text-secondary': 'var(--mars-color-text-secondary)',
          'text-tertiary': 'var(--mars-color-text-tertiary)',
          border: 'var(--mars-color-border)',
          'border-strong': 'var(--mars-color-border-strong)',
          success: 'var(--mars-color-success)',
          warning: 'var(--mars-color-warning)',
          danger: 'var(--mars-color-danger)',
          info: 'var(--mars-color-info)',
        },
        // Preserve existing colors for backward compat during migration
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        console: {
          bg: '#1a1a1a',
          text: '#e5e5e5',
          success: '#22c55e',
          error: '#ef4444',
          warning: '#f59e0b',
          info: '#3b82f6',
        }
      },
      fontFamily: {
        sans: ['var(--mars-font-sans)'],
        mono: ['var(--mars-font-mono)'],
      },
      borderRadius: {
        'mars-sm': 'var(--mars-radius-sm)',
        'mars-md': 'var(--mars-radius-md)',
        'mars-lg': 'var(--mars-radius-lg)',
        'mars-xl': 'var(--mars-radius-xl)',
      },
      boxShadow: {
        'mars-sm': 'var(--mars-shadow-sm)',
        'mars-md': 'var(--mars-shadow-md)',
        'mars-lg': 'var(--mars-shadow-lg)',
        'mars-xl': 'var(--mars-shadow-xl)',
      },
      zIndex: {
        'dropdown': 'var(--mars-z-dropdown)',
        'sticky': 'var(--mars-z-sticky)',
        'nav': 'var(--mars-z-nav)',
        'modal-backdrop': 'var(--mars-z-modal-backdrop)',
        'modal': 'var(--mars-z-modal)',
        'toast': 'var(--mars-z-toast)',
        'tooltip': 'var(--mars-z-tooltip)',
      },
      transitionTimingFunction: {
        'mars': 'var(--mars-ease-standard)',
        'mars-bounce': 'var(--mars-ease-bounce)',
      },
      transitionDuration: {
        'mars-fast': 'var(--mars-duration-fast)',
        'mars-normal': 'var(--mars-duration-normal)',
        'mars-slow': 'var(--mars-duration-slow)',
      },
      spacing: {
        'sidenav': 'var(--mars-sidenav-width)',
        'sidenav-collapsed': 'var(--mars-sidenav-collapsed-width)',
        'topbar': 'var(--mars-topbar-height)',
      },
    },
  },
  plugins: [],
}
