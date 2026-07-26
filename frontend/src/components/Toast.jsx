import { useState, useEffect } from "react"

const listeners = []

export const toast = {
    success: (msg) => emit("success", msg),
    error: (msg) => emit("error", msg),
    info: (msg) => emit("info", msg),
}

function emit(type, message) {
    const id = Date.now() + Math.random()
    listeners.forEach(fn => fn({ id, type, message }))
}

export function ToastContainer() {
    const [toasts, setToasts] = useState([])

    useEffect(() => {
        const handler = (t) => {
            setToasts(prev => [...prev, t])
            setTimeout(() => {
                setToasts(prev => prev.filter(x => x.id !== t.id))
            }, 3000)
        }
        listeners.push(handler)
        return () => {
            const idx = listeners.indexOf(handler)
            if (idx > -1) listeners.splice(idx, 1)
        }
    }, [])

    const colors = {
        success: "bg-green-500/15 border-green-400/30 text-green-400",
        error: "bg-red-500/15 border-red-400/30 text-red-400",
        info: "bg-primary/15 border-primary/30 text-primary",
    }

    const icons = { success: "✓", error: "✗", info: "ℹ" }

    if (toasts.length === 0) return null

    return (
        <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2">
            {toasts.map(t => (
                <div
                    key={t.id}
                    className={`flex items-center gap-3 px-4 py-3 rounded-xl border text-sm font-medium shadow-soft animate-slide-up ${colors[t.type]}`}
                >
                    <span className="text-base">{icons[t.type]}</span>
                    {t.message}
                </div>
            ))}
        </div>
    )
}
