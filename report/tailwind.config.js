/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './core/templates/**/*.html',
    './orders/templates/**/*.html',
    './users/templates/**/*.html',
    './static/js/**/*.js',
    './orders/static/**/*.js'
  ],
  theme: {
    extend: {}
  },
  plugins: []
};
