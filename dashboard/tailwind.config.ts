import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1c1612",
        ivory: "#f5efe3",
        terracotta: "#b24b34",
        olive: "#5c6650",
        gold: "#c59a46",
        stone: "#d8cec0",
        night: "#15100d"
      },
      boxShadow: {
        card: "0 24px 60px -28px rgba(29, 22, 18, 0.35)"
      },
      backgroundImage: {
        grain:
          "radial-gradient(circle at 12% 16%, rgba(197,154,70,0.18), transparent 0 26%), radial-gradient(circle at 86% 0%, rgba(178,75,52,0.16), transparent 0 28%), linear-gradient(140deg, rgba(247,240,229,0.96), rgba(239,228,212,0.92))"
      }
    }
  },
  plugins: []
};

export default config;
