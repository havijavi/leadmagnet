import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Light theme — warm off-white / cream
        bg: "#fafaf7",      // page background, very subtle warm cream
        panel: "#ffffff",   // card/panel surfaces, pure white
        panel2: "#f4f3ef",  // slightly tinted nested surfaces (inputs, hover)
        border: "#e5e3dc",  // soft cream borders
        text: "#1f2937",    // dark slate text for body content
        muted: "#6b7280",   // secondary text / labels
        accent: "#6d4cff",  // brand purple (slightly deeper for contrast on white)
        accent2: "#0891b2", // cyan for links / highlights
        good: "#16a34a",
        warn: "#d97706",
        bad: "#dc2626",
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "Inter", "sans-serif"],
        mono: ["ui-monospace", "SF Mono", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
