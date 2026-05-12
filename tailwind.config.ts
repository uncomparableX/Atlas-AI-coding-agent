import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#030712", // slate-950
        foreground: "#f8fafc", // slate-50
        surface: "rgba(255, 255, 255, 0.03)",
        "surface-elevated": "rgba(255, 255, 255, 0.06)",
        border: "rgba(255, 255, 255, 0.08)",
        ring: "rgba(99, 102, 241, 0.3)",
        accent: {
          DEFAULT: "#22d3ee", // cyan-400
          glow: "rgba(34, 211, 238, 0.4)",
          secondary: "#8b5cf6", // violet-500
        },
        success: "#34d399", // emerald-400
        warning: "#fbbf24", // amber-400
        error: "#f87171", // red-400
        terminal: {
          bg: "#0c0c0c",
          text: "#e2e8f0",
          green: "#4ade80",
          blue: "#60a5fa",
          purple: "#c084fc",
          yellow: "#facc15",
        },
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui"],
        mono: ["var(--font-geist-mono)", "monospace"],
      },
      animation: {
        "pulse-glow": "pulse-glow 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "float": "float 6s ease-in-out infinite",
        "stream": "stream 1s linear infinite",
        "cursor-blink": "cursor-blink 1s step-end infinite",
        "slide-up": "slide-up 0.5s ease-out",
        "fade-in": "fade-in 0.3s ease-out",
      },
      keyframes: {
        "pulse-glow": {
          "0%, 100%": { opacity: "1", boxShadow: "0 0 20px rgba(34,211,238,0.3)" },
          "50%": { opacity: "0.7", boxShadow: "0 0 10px rgba(34,211,238,0.1)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-20px)" },
        },
        stream: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "cursor-blink": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0" },
        },
        "slide-up": {
          "0%": { transform: "translateY(10px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
      },
      backdropBlur: {
        xs: "2px",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
