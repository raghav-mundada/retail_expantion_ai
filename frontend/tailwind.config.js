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
        // Warm parchment palette — premium editorial, like a well-aged research report
        ink:       "#2C1810",      // deep espresso — primary text
        graphite:  "#5C3D1E",      // warm brown — secondary text
        slate:     "#8B6F4E",      // warm taupe — tertiary
        mist:      "#B8956A",      // warm tan — muted
        hairline:  "#D4BFA0",      // warm beige — dividers
        bone:      "#EDE0D4",      // warm bone — surface tint
        paper:     "#F5EFE6",      // parchment — page background
        snow:      "#FBF7F2",      // warm white — cards

        // Warm accent system
        warm:      "#C8A882",      // mid-tone warm — interactive surfaces
        mocha:     "#A07850",      // deeper warm — hover accents
        sienna:    "#5C3D1E",      // espresso — deep accent
        caramel:   "#C8A882",      // alias for warm

        // Functional / status (kept intentional)
        emerald:   "#2D6A4F",      // GO / positive (warmer green)
        amber:     "#B45309",      // CAUTION
        crimson:   "#B91C1C",      // STOP / risk

        // Data viz (warm tones)
        chart: {
          1: "#5C8A5A",
          2: "#7C4A1E",
          3: "#3B6EA8",
          4: "#7B4F8E",
          5: "#B45309",
        },
      },
      letterSpacing: {
        tightest: "-0.04em",
        snug: "-0.02em",
      },
      animation: {
        "fade-up":    "fadeUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        "fade-in":    "fadeIn 0.4s ease-out forwards",
        "ping-slow":  "ping 2.4s cubic-bezier(0, 0, 0.2, 1) infinite",
        "shimmer":    "shimmer 1.8s ease-in-out infinite",
        "count-up":   "fadeUp 0.4s cubic-bezier(0.16,1,0.3,1) forwards",
        "glow-pulse": "glowPulse 2s ease-in-out infinite",
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
        shimmer: {
          "0%":   { backgroundPosition: "-200% center" },
          "100%": { backgroundPosition: "200% center" },
        },
        glowPulse: {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(200,168,130,0)" },
          "50%":       { boxShadow: "0 0 20px 4px rgba(200,168,130,0.18)" },
        },
      },
    },
  },
  plugins: [],
};
