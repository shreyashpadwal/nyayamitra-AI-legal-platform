import { useState, useEffect } from "react"
import { apiGet, BASE_URL } from "../utils/auth"

export default function CasesBrowser() {
    const [cases, setCases] = useState([])
    const [loading, setLoading] = useState(true)
    const [search, setSearch] = useState("")
    const [error, setError] = useState("")

    useEffect(() => {
        apiGet("/lawyer/cases")
            .then(setCases)
            .catch(e => setError(e.message))
            .finally(() => setLoading(false))
    }, [])

    const filtered = cases.filter(c =>
        c.case_name?.toLowerCase().includes(search.toLowerCase()) ||
        String(c.year).includes(search)
    )

    if (loading) return (
        <div className="flex justify-center items-center py-20">
            <div className="spinner-gold" /><span className="ml-3 text-gray-400">Loading cases…</span>
        </div>
    )

    return (
        <div>
            <div className="flex items-center justify-between mb-6 gap-4">
                <div>
                    <h2 className="text-xl font-bold text-white">📁 Case Browser</h2>
                    <p className="text-gray-500 text-sm mt-0.5">{cases.length} indexed Supreme Court judgments</p>
                </div>
            </div>

            {error && (
                <div className="bg-red-500/10 border border-red-400/30 rounded-xl px-4 py-3 text-red-400 text-sm mb-4">
                    {error} — Make sure the FAISS index is built and the backend is running.
                </div>
            )}

            {/* Search */}
            <input
                type="text"
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search by case name or year…"
                className="input-gold mb-5"
            />

            {!cases.length && !error ? (
                <div className="text-center py-16">
                    <div className="text-5xl mb-4">🏛️</div>
                    <p className="text-gray-400">No cases indexed yet.</p>
                    <p className="text-gray-500 text-sm mt-2">Run <code className="text-gold bg-gold/10 px-2 py-0.5 rounded">python scripts/download_judgments.py</code> and <code className="text-gold bg-gold/10 px-2 py-0.5 rounded">build_faiss_index.py</code> first.</p>
                </div>
            ) : (
                <div className="space-y-2">
                    {filtered.map(c => (
                        <div key={c.id} className="card px-5 py-4 flex items-center justify-between hover:border-gold/30 transition-all duration-200">
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-1 flex-wrap">
                                    {c.year && <span className="badge-lawyer">{c.year}</span>}
                                    <span className="badge-criminal">{c.case_type || "Criminal"}</span>
                                </div>
                                <p className="text-white text-sm font-medium truncate">{c.case_name || "Untitled Case"}</p>
                            </div>
                            {c.link && (
                                <a
                                    href={c.link.startsWith("http") ? c.link : `${BASE_URL}${c.link}`}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="ml-4 flex-shrink-0 text-gold hover:text-goldLight text-xs border border-gold/30 hover:border-gold/60 px-3 py-1.5 rounded-lg transition-all"
                                >
                                    View →
                                </a>
                            )}
                        </div>
                    ))}
                    {filtered.length === 0 && (
                        <div className="text-center py-10 text-gray-500">No matching cases found.</div>
                    )}
                </div>
            )}
        </div>
    )
}
