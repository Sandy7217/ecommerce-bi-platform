import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./frontend/app/**/*.{ts,tsx}", "./frontend/components/**/*.{ts,tsx}", "./frontend/lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172033",
        muted: "#64748b",
        line: "#dbe3ee",
        surface: "#ffffff",
        canvas: "#f6f8fb",
        teal: "#0f9488",
        blue: "#2563eb",
        amber: "#d97706",
        danger: "#dc2626"
      },
      boxShadow: {
        soft: "0 8px 24px rgba(23, 32, 51, 0.08)"
      }
    }
  },
  plugins: []
};

export default config;
