/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./pages/**/*.{js,jsx}",
    "./components/**/*.{js,jsx}"
  ],
  theme: {
    extend: {
      colors: {
        pirateBlue: '#1E3A8A',
        pirateGold: '#D4AF37',
        pirateBlack: '#0B0C10',
        pirateGray: '#4B5563'
      },
      fontFamily: {
        pirate: ['"Pirata One"', 'cursive'],
        sans: ['Inter', 'sans-serif']
      }
    },
  },
  plugins: [],
}
