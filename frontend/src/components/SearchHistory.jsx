import { useState, useEffect } from "react"
import { apiGet, apiDelete } from "../utils/auth"

export default function SearchHistory({ onReopen }) {
    const [history, setHistory] = useState([])
    const [loading, setLoading] = useState(true)
    const [deleting, setDeleting] = useState(null)

    useEffect(() => {
        apiGet("/lawyer/history")
            .then(data => {
                const sorted = [...data].sort(
                    (a, b) => new Date(b.timestamp) - new Date(a.timestamp)
                )
                setHistory(sorted)
            })
            .catch(console.error)
            .finally(() => setLoading(false))
    }, [])

    const fmt = iso => new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })

    const handleDelete = async (id, e) => {
        e.stopPropagation()
        if (!window.confirm("Delete this search from history? This cannot be undone.")) return
        setDeleting(id)
        try {
            await apiDelete(`/lawyer/history/${id}`)
            setHistory(prev => prev.filter(s => s.id !== id))
        } catch (err) {
            alert("Delete failed: " + err.message)
        } finally {
            setDeleting(null)
        }
    }

    const handleReopen = (s) => {
        if (!onReopen) return
        let cases = []
        try { cases = JSON.parse(s.results_json || "[]") } catch { cases = [] }
        onReopen({
            query:    s.query,
            cases,
            strategy: s.strategy_text || null,   // null for pre-fix rows
        })
    }

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
                            onClick={() => handleReopen(s)}
                            title="Click to reopen in Case Similarity tab"
                        >
                            <div className="flex-1 min-w-0">
                                <p className="text-white text-sm font-medium truncate">{s.query}</p>
                                <div className="flex items-center gap-3 mt-1">
                                    <p className="text-gray-500 text-xs">{fmt(s.timestamp)}</p>
                                    {s.strategy_text
                                        ? <span className="text-[10px] text-gold/70 bg-gold/10 px-2 py-0.5 rounded-full border border-gold/20">Strategy saved</span>
                                        : <span className="text-[10px] text-gray-600 bg-surfaceLight px-2 py-0.5 rounded-full border border-border">Cases only</span>
                                    }
                                </div>
                            </div>
                            <div className="flex items-center gap-2 ml-4 flex-shrink-0">
                                {/* Delete button */}
                                <button
                                    onClick={(e) => handleDelete(s.id, e)}
                                    disabled={deleting === s.id}
                                    className="w-7 h-7 flex items-center justify-center rounded-lg bg-transparent hover:bg-red-500/20 text-gray-600 hover:text-red-400 transition-colors disabled:opacity-40"
                                    title="Delete this search"
                                >
                                    {deleting === s.id
                                        ? <div className="spinner-gold w-3 h-3 !border-red-400" />
                                        : "🗑"}
                                </button>
                                {/* Reopen hint */}
                                <span className="text-gray-500 text-sm" title="Click row to reopen">↩</span>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    )
}
