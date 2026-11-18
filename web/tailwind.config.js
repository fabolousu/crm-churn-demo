/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#F6F4EF",
        surface: "#FFFFFF",
        ink: "#14181F",
        muted: "#5B6472",
        line: "#E5E0D6",
        accent: {
          DEFAULT: "#0F6B5C",
          soft: "#E3EFEA",
          deep: "#0A4A40",
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
