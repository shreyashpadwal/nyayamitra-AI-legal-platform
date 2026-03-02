import { useState, useEffect } from "react"
import { apiGet } from "../utils/auth"

export default function SearchHistory() {
    const [history, setHistory] = useState([])
    const [loading, setLoading] = useState(true)
    const [expanded, setExpanded] = useState(null)

    useEffect(() => {
        apiGet("/lawyer/history")
            .then(setHistory)
            .catch(console.error)
            .finally(() => setLoading(false))
    }, [])

    const fmt = iso => new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })

    if (loading) return (
        <div className="flex justify-center items-center py-20">
            <div className="spinner-gold" /><span className="ml-3 text-gray-400">Loading history…</span>
        </div>
    )

    if (!history.length) return (
        <div className="text-center py-20">
            <div className="text-5xl mb-4">📋</div>
            <p className="text-gray-400">No searches yet. Run a case similarity search first.</p>
        </div>
    )

    return (
        <div>
            <h2 className="text-xl font-bold text-white mb-6">📋 Search History</h2>
            <div className="space-y-3">
                {history.map(s => (
                    <div key={s.id} className="card overflow-hidden">
                        <div
                            className="px-5 py-4 flex justify-between items-center cursor-pointer hover:bg-surfaceLight transition-colors"
                            onClick={() => setExpanded(expanded === s.id ? null : s.id)}
                        >
                            <div className="flex-1 min-w-0">
                                <p className="text-white text-sm font-medium truncate">{s.query}</p>
                                <p className="text-gray-500 text-xs mt-1">{fmt(s.timestamp)}</p>
                            </div>
                            <span className="text-gray-500 text-lg ml-4 flex-shrink-0">
                                {expanded === s.id ? "▲" : "▼"}
                            </span>
                        </div>
                        {expanded === s.id && (
                            <div className="border-t border-border px-5 py-4 bg-bg">
                                <p className="text-gray-400 text-xs font-semibold uppercase tracking-wider mb-2">Case Query</p>
                                <p className="text-gray-200 text-sm leading-relaxed">{s.query}</p>
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>
    )
}
