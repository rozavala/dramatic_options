/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: { 900: "#0f1b32", 700: "#1d2c46", 600: "#2a3c5e" },
        canvas: "#fafbfc",
        ink: { DEFAULT: "#141b28", 2: "#2c3645", 3: "#414956", 4: "#5f6675", faint: "#8b919b" },
        accent: "#1558d6",
        cardborder: "#cbd0da",
      },
      fontFamily: {
        sans: ["Roboto", "system-ui", "sans-serif"],
        mono: ["'Roboto Mono'", "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px 0 rgba(60,64,67,0.10), 0 1px 3px 1px rgba(60,64,67,0.05)",
        cardhover: "0 1px 3px 0 rgba(60,64,67,0.16), 0 4px 8px 3px rgba(60,64,67,0.10)",
      },
      borderRadius: { card: "16px" },
    },
  },
  plugins: [],
};
