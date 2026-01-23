/**
 * PostCSS Configuration for D-code UI
 * 
 * This configuration enables:
 * - Tailwind CSS for utility-first styling
 * - Autoprefixer for cross-browser compatibility
 */
export default {
  plugins: {
    // Tailwind CSS
    // Processes @tailwind directives and generates utility classes
    tailwindcss: {},
    
    // Autoprefixer
    // Adds vendor prefixes for cross-browser compatibility
    // Uses browserslist config from package.json
    autoprefixer: {},
  },
};
