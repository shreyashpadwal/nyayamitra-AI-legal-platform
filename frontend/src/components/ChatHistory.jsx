import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { apiGet, apiDelete } from "../utils/auth"

export default function ChatHistory() {
    const [history, setHistory] = useState([])
    const [loading, setLoading] = useState(true)
    const [expanded, setExpanded] = useState(null)
    const navigate = useNavigate()

    useEffect(() => { fetchHistory() }, [])

    const fetchHistory = async () => {
        try {
            const data = await apiGet("/citizen/history")
            setHistory(data)
        } catch (e) { console.error(e) }
        finally { setLoading(false) }
    }

    const handleDelete = async (id, e) => {
        e.stopPropagation()
        try {
            await apiDelete(`/citizen/history/${id}`)
            setHistory(h => h.filter(c => c.id !== id))
            if (expanded === id) setExpanded(null)
        } catch (e) { console.error(e) }
    }

    const fmt = iso => new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })

    if (loading) return (
        <div className="flex justify-center items-center py-20">
            <div className="spinner" />
            <span className="ml-3 text-gray-400">Loading history…</span>
        </div>
    )

    if (!history.length) return (
        <div className="text-center py-20">
            <div className="text-5xl mb-4">📭</div>
            <p className="text-gray-400 mb-6">No conversations yet.</p>
            <button onClick={() => navigate("/chat")} className="btn-primary">Start Chatting</button>
        </div>
    )

    return (
        <div>
            <h2 className="text-xl font-bold text-white mb-6">🕐 Chat History</h2>
            <div className="space-y-3">
                {history.map(item => (
                    <div key={item.id} className="card overflow-hidden">
                        {/* Header row */}
                        <div
                            className="px-5 py-4 flex justify-between items-center cursor-pointer hover:bg-surfaceLight transition-colors"
                            onClick={() => setExpanded(expanded === item.id ? null : item.id)}
                        >
                            <div className="flex-1 min-w-0">
                                <p className="text-white text-sm font-medium truncate">{item.question}</p>
                                <p className="text-gray-500 text-xs mt-1">{fmt(item.timestamp)}</p>
                            </div>
                            <div className="flex gap-2 ml-4 flex-shrink-0">
                                <button
                                    onClick={e => { e.stopPropagation(); navigate("/chat", { state: { historyItem: item } }) }}
                                    className="text-primary border border-primary/30 hover:bg-primary/10 px-3 py-1.5 rounded-lg text-xs transition-all"
                                >
                                    Continue
                                </button>
                                <button onClick={e => handleDelete(item.id, e)} className="btn-danger text-xs px-3 py-1.5">
                                    Delete
                                </button>
                                <span className="text-gray-500 text-lg self-center">
                                    {expanded === item.id ? "▲" : "▼"}
                                </span>
                            </div>
                        </div>
                        {/* Expanded */}
                        {expanded === item.id && (
                            <div className="border-t border-border px-5 py-4 bg-bg">
                                <p className="text-gray-400 text-xs font-semibold uppercase tracking-wider mb-2">Your Question</p>
                                <p className="text-white text-sm mb-4">{item.question}</p>
                                <p className="text-gray-400 text-xs font-semibold uppercase tracking-wider mb-2">AI Answer</p>
                                <p className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap">{item.answer}</p>
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>
    )
}
