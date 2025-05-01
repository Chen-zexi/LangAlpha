/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './static/**/*.js',
  ],
  darkMode: 'media',
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#EFF6FF',
          100: '#DBEAFE',
          200: '#BFDBFE',
          300: '#93C5FD',
          400: '#60A5FA',
          500: '#3B82F6',
          600: '#2563EB',
          700: '#1D4ED8',
          800: '#1E40AF',
          900: '#1E3A8A',
        },
        agent: {
          coordinator: '#5AC8F5',
          planner: '#C7F572',
          supervisor: '#A4CA7A',
          researcher: '#95C98D',
          market: '#30B0C7',
          coder: '#8FD396',
          browser: '#F28AB5',
          analyst: '#FFD60A',
          reporter: '#AF8CFF',
        }
      },
      animation: {
        'typing-dot': 'typingDot 1.5s infinite ease-in-out',
        'fade-in': 'fadeIn 0.3s ease-in',
        'fade-in-up': 'fadeInUp 0.5s ease-out',
        'pulse': 'pulse 2s infinite',
      },
      keyframes: {
        typingDot: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-3px)' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        fadeInUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulse: {
          '0%, 100%': { opacity: '0.8', transform: 'scale(0.8)' },
          '50%': { opacity: '1', transform: 'scale(1.2)' },
        }
      }
    }
  },
  plugins: [],
} 