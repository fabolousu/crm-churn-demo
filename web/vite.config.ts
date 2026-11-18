import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The demo runs offline on fixtures by default. Set VITE_API_BASE to point the
// same UI at the FastAPI service (see web/README.md).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
  },
  preview: {
    port: 4173,
  },
});
