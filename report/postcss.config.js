module.exports = {
  plugins: [
    require('postcss-import')({
      path: ['node_modules', './static/src']
    }),
    require('tailwindcss'),
    require('autoprefixer')
  ]
};
