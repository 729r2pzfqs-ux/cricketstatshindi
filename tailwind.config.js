/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./scripts/**/*.py",
    "./**/*.html",
    "!./node_modules/**",
  ],
  theme: {
    extend: {
      colors: {
        'cr-green':  '#15803d',
        'cr-dark':   '#14532d',
        'cr-accent': '#22c55e',
        'cr-bg':     '#f5f8f4',
        'cr-card':   '#ffffff',
        'cr-border': '#e2e8e0',
        'cr-text':   '#52635a',
        'cr-ink':    '#16241b',
        'cr-pitch':  '#c9b079',
        'cr-ball':   '#a4161a',
      },
      fontFamily: {
        heading: ['"Baloo 2"', '"Noto Sans Devanagari"', 'sans-serif'],
        body:    ['Inter', '"Noto Sans Devanagari"', 'sans-serif'],
      },
    },
  },
}
