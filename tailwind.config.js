/** Tailwind v3 config, used by the standalone CLI (no Node/npm needed). */
module.exports = {
  content: ["./templates/**/*.html", "./**/templates/**/*.html", "./static/js/**/*.js"],
  theme: {
    extend: {
      colors: {
        // Named brand colours. All text/background pairs used meet WCAG AA.
        cream: "#FBF7F0",      // page background
        sand: "#F1E9DC",       // subtle panels, borders
        ink: "#1F2933",        // main text (15:1 on cream)
        muted: "#52606D",      // secondary text (6.2:1 on cream)
        accent: {
          DEFAULT: "#C2410C",  // buttons; white text 5.2:1
          dark: "#9A3412",     // hover / pressed
          soft: "#FFEDD5",     // highlights
        },
        leaf: {
          DEFAULT: "#2F7A5B",  // success / done; white text 5.1:1
          soft: "#E3F2EA",
        },
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif"],
      },
      borderRadius: { card: "1.25rem" },
      minHeight: { tap: "48px" },
    },
  },
  plugins: [],
};
