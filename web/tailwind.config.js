/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#FFFFFF",
        surface: "#FFFFFF",
        ink: "#19242E",
        muted: "#5B6472",
        line: "#DBE2E8",
        accent: {
          DEFAULT: "#005EB8",
          soft: "#CBE4FB",
          deep: "#00499D",
        },
        brand: {
          DEFAULT: "#005EB8",
          dark: "#00499D",
          soft: "#CBE4FB",
          ink: "#19242E",
          surface: "#EEF2F5",
          border: "#DBE2E8",
          strong: "#AFBAC4",
          green: "#88E771",
          red: "#E74C3C",
        },
        copper: "#B4693A",
        risk: {
          low: "#067647",
          medium: "#B54708",
          high: "#B42318",
          critical: "#7A271A",
        },
      },
      fontFamily: {
        sans: [
          "DM Sans",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        display: [
          "DM Sans",
          "Iowan Old Style",
          "Palatino Linotype",
          "Palatino",
          "Georgia",
          "serif",
        ],
      },
      boxShadow: {
        card: "0 1px 2px rgba(20, 24, 31, 0.04), 0 8px 24px -16px rgba(20, 24, 31, 0.18)",
      },
    },
  },
  plugins: [],
};
