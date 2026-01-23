/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Discord-inspired dark theme
        'dc-dark': {
          50: '#f5f5f5',
          100: '#eaeaeb',
          200: '#dcddde',
          300: '#b9bbbe',
          400: '#8e9297',
          500: '#72767d',
          600: '#4f545c',
          700: '#36393f',
          800: '#2f3136',
          900: '#202225',
          950: '#18191c',
        },
        'dc-accent': {
          primary: '#5865f2',
          success: '#3ba55d',
          warning: '#faa81a',
          danger: '#ed4245',
          info: '#00b0f4',
        },
      },
      fontFamily: {
        'mono': ['JetBrains Mono', 'Fira Code', 'Monaco', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'typing': 'typing 1s ease-in-out infinite',
      },
      keyframes: {
        typing: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
      },
    },
  },
  plugins: [],
}
