/** @type {import('tailwindcss').Config} */
export default {
    content: ["./index.html", "./src/**/*.{js,jsx}"],
    theme: {
        extend: {
            colors: {
                bg: "#08090f",
                surface: "#0f1117",
                surfaceLight: "#161927",
                border: "#1e2235",
                primary: "#6366f1",
                accent: "#818cf8",
                gold: "#f59e0b",
                goldLight: "#fbbf24",
            },
            fontFamily: {
                sans: ["Inter", "sans-serif"],
            },
            boxShadow: {
                glow: "0 0 24px rgba(99,102,241,0.25)",
                goldglow: "0 0 24px rgba(245,158,11,0.25)",
                soft: "0 4px 24px rgba(0,0,0,0.4)",
            },
            backgroundImage: {
                "hero-gradient": "radial-gradient(ellipse 80% 60% at 50% -10%, rgba(99,102,241,0.18) 0%, transparent 70%)",
                "gold-gradient": "radial-gradient(ellipse 80% 60% at 50% -10%, rgba(245,158,11,0.15) 0%, transparent 70%)",
            }
        },
    },
    plugins: [],
}
