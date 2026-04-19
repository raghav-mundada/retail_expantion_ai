/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        // Distinctive editorial display + clean modern body + technical mono
        display: ['"Instrument Serif"', "Georgia", "serif"],
        sans: ['"Geist"', "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ['"Geist Mono"', "ui-monospace", "monospace"],
      },
      colors: {
        // Premium light palette — like a private equity research report
        ink:       "#0A0A0A",      // primary text
        graphite:  "#3F3F46",      // secondary text
        slate:     "#71717A",      // tertiary
        mist:      "#A1A1AA",      // muted
        hairline:  "#E4E4E7",      // dividers
        bone:      "#F5F5F4",      // surface tint
        paper:     "#FAFAF9",      // page background
        snow:      "#FFFFFF",      // pure card

        // Single jewel accent + status
        emerald:   "#047857",      // GO / positive
        amber:     "#B45309",      // CAUTION
        crimson:   "#B91C1C",      // STOP / risk

        // Subtle data viz hues (muted, editorial)
        chart: {
          1: "#0F766E",
          2: "#7C2D12",
          3: "#1E40AF",
          4: "#86198F",
          5: "#B45309",
        },
      },
      letterSpacing: {
        tightest: "-0.04em",
        snug: "-0.02em",
      },
      animation: {
        "fade-up":   "fadeUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        "fade-in":   "fadeIn 0.4s ease-out forwards",
        "ping-slow": "ping 2.4s cubic-bezier(0, 0, 0.2, 1) infinite",
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: 0, transform: "translateY(12px)" },
          "100%": { opacity: 1, transform: "translateY(0)" },
        },
        fadeIn: {
          "0%": { opacity: 0 },
          "100%": { opacity: 1 },
        },
      },
    },
  },
  plugins: [],
};
