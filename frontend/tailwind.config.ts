import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#1c2a1f",
        foreground: "#f0ebe5",
        border: "#3e4a3d",
        input: "#3e4a3d",
        primary: {
          DEFAULT: "#4caf50",
          foreground: "#0a1f0c"
        },
        muted: {
          DEFAULT: "#2d3a2e",
          foreground: "#d7cfc4"
        },
        ring: "#4caf50",
        destructive: {
          DEFAULT: "#ef4444",
          foreground: "#f0ebe5"
        }
      }
    }
  },
  plugins: []
};

export default config;
