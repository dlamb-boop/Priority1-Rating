import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#f4f1ea",
        card: "#fffdf8",
        ink: "#14241c",
        pine: "#0f6e56",
        "pine-deep": "#0c3d32",
        line: "#e2d9c9",
        moss: "#e7f3ee",
      },
      fontFamily: {
        sans: ["Inter", "Segoe UI", "Helvetica Neue", "Arial", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        desk: "0 1px 0 rgba(20, 36, 28, 0.04), 0 12px 32px rgba(20, 36, 28, 0.06)",
      },
    },
  },
  plugins: [],
};

export default config;
