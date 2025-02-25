/** @type {import('@tailwindcss/postcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'option-green': '#10B981',
        'option-red': '#EF4444',
      },
    },
  },
  plugins: [],
} 