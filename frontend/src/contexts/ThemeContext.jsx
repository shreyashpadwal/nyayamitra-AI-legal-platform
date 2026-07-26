import { createContext, useContext, useEffect, useState } from "react"

const ThemeContext = createContext()

export function ThemeProvider({ children }) {
    const [theme, setTheme] = useState(() => {
        const saved = localStorage.getItem("nyaya_theme")
        if (saved) return saved
        return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "dark"
    })

    useEffect(() => {
        const root = document.documentElement
        root.setAttribute("data-theme", theme)
        localStorage.setItem("nyaya_theme", theme)
    }, [theme])

    const toggle = () => setTheme(t => t === "dark" ? "light" : "dark")

    return (
        <ThemeContext.Provider value={{ theme, toggle, isDark: theme === "dark" }}>
            {children}
        </ThemeContext.Provider>
    )
}

export const useTheme = () => useContext(ThemeContext)
