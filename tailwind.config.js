/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.js"
  ],
  theme: {
    extend: {
      colors: {
        // VoltX Cyberpunk Color Palette
        'dark': {
          DEFAULT: '#050508',
          'lighter': '#0a0a12',
          'light': '#0f0f18',
          'surface': '#14141f',
          'elevated': '#18182a'
        },
        'neon': {
          'cyan': '#00f0ff',
          'green': '#39ff14',
          'magenta': '#ff00ff',
          'pink': '#ff2d92',
          'purple': '#8b5cf6',
          'violet': '#a855f7',
          'red': '#ff003c',
          'orange': '#ff6b35',
          'yellow': '#ffd000',
          'amber': '#f59e0b',
          'blue': '#3b82f6'
        }
      },
      fontFamily: {
        'display': ['Orbitron', 'Space Grotesk', 'sans-serif'],
        'body': ['Space Grotesk', 'Inter', 'sans-serif'],
        'mono': ['JetBrains Mono', 'Fira Code', 'monospace'],
        'cyber': ['Orbitron', 'monospace']
      },
      borderRadius: {
        'sm': '4px',
        'md': '8px',
        'lg': '12px',
        'xl': '16px',
        '2xl': '24px'
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2s ease-in-out infinite alternate'
      },
      keyframes: {
        glow: {
          '0%': { boxShadow: '0 0 20px rgba(0, 240, 255, 0.3)' },
          '100%': { boxShadow: '0 0 40px rgba(0, 240, 255, 0.6)' }
        }
      }
    }
  },
  plugins: []
}
