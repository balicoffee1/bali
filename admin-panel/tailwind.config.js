/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      screens: {
        // Узкий брейкпоинт для полей внутри диалогов на маленьких экранах
        xs: '420px',
      },
      colors: {
        brand: {
          lime: '#AEEC2A',
          'lime-hover': '#9ad522',
          green: '#86C600',
          'green-text': '#73A900',
          dark: '#2B2D31',
          'dark-blue': '#475569',
          'gray-blue': '#94A3B8',
          'light-gray': '#F1F5F9',
          orange: '#FF9900',
          yellow: '#FFB800',
          red: '#F9635B',
          'coral-red': '#FF847D',
          blue: '#3384FF',
          purple: '#CE8FF4',
        },
      },
      fontFamily: {
        montserrat: ['Montserrat', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        'r8': '8px',
        'r12': '12px',
        'r18': '18px',
        'r31': '31px',
      },
      boxShadow: {
        card: '0 2px 10px rgba(0, 0, 0, 0.04)',
        hover: '0 10px 25px -5px rgba(0, 0, 0, 0.08), 0 8px 10px -6px rgba(0, 0, 0, 0.04)',
        drawer: '-4px 0 24px rgba(0, 0, 0, 0.12)',
      },
    },
  },
  plugins: [],
}
