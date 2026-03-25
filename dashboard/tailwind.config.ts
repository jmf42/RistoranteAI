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
        night: "#261c19"
      },
      boxShadow: {
        card: "0 24px 60px -28px rgba(29, 22, 18, 0.35)"
      },
      backgroundImage: {
        grain:
          "radial-gradient(circle at 20% 20%, rgba(197,154,70,0.18), transparent 0 30%), radial-gradient(circle at 80% 0%, rgba(178,75,52,0.16), transparent 0 32%), linear-gradient(135deg, rgba(245,239,227,0.96), rgba(232,222,206,0.92))"
      }
    }
  },
  plugins: []
};

export default config;
