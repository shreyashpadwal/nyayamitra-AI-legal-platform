import { useState, useEffect, useRef } from "react"
import { BASE_URL, API, getToken, authHeaders } from "../utils/auth"
import { downloadDOCX } from "../utils/documents"
import ReactMarkdown from "react-markdown"

// ---------------------------------------------------------------------------
// CaseCard — rank, case name, type/year badges, excerpt, PDF link.
// Similarity % / progress bar and Analyze Deeply removed.
// ---------------------------------------------------------------------------
function CaseCard({ c, index }) {
    const [expanded, setExpanded] = useState(false)

    return (
        <div className="card-gold p-5">
            <div className="mb-3">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="text-gold font-bold text-sm">#{index + 1}</span>
                    <span className="badge-criminal">{c.case_type || "Criminal"}</span>
                    {c.year && c.year !== "N/A" && <span className="text-gray-500 text-xs">{c.year}</span>}
                </div>
                <h3 className="text-white font-semibold text-sm leading-snug">{c.case_name}</h3>
            </div>

            <p className={`text-gray-400 text-xs leading-relaxed ${expanded ? "" : "line-clamp-2"}`}>
                {c.excerpt}
            </p>
            <button onClick={() => setExpanded(!expanded)} className="text-gold text-xs mt-1 hover:opacity-80 transition-opacity">
                {expanded ? "Show less ▲" : "Read more ▼"}
            </button>

            <div className="flex gap-3 mt-4">
                {c.link ? (
                    <a href={c.link.startsWith("http") ? c.link : `${BASE_URL}${c.link}`} target="_blank" rel="noreferrer" className="flex-1 border border-border text-gray-400 py-1.5 rounded-lg text-xs font-semibold hover:border-gold/40 hover:text-white transition-all text-center">
                        📄 View PDF
                    </a>
                ) : c.pdf_path && (
                    <a href={`${BASE_URL}/data/judgments/${c.pdf_path.split(/[/\\]/).pop()}`} target="_blank" rel="noreferrer" className="flex-1 border border-border text-gray-400 py-1.5 rounded-lg text-xs font-semibold hover:border-gold/40 hover:text-white transition-all text-center">
                        📄 View PDF
                    </a>
                )}
            </div>
        </div>
    )
}

// ---------------------------------------------------------------------------
// Main SimilaritySearch component
// ---------------------------------------------------------------------------
export default function SimilaritySearch({ initialData, onClearReopen }) {
    const [query, setQuery]         = useState("")
    const [k, setK]                 = useState(5)
    const [results, setResults]     = useState(null)
    const [strategy, setStrategy]   = useState("")
    const [loading, setLoading]     = useState(false)
    const [statusMsg, setStatusMsg] = useState("")   // live SSE stage text
    const [error, setError]         = useState("")
    const [showCases, setShowCases] = useState(false)
    const [isReopened, setIsReopened] = useState(false)
    const [copied, setCopied]       = useState(false)  // brief "Copied!" flash
    const abortRef = useRef(null)  // holds AbortController for in-flight SSE

    // ── Action helpers ────────────────────────────────────────────────────
    const handleCopy = () => {
        if (!strategy) return
        navigator.clipboard.writeText(strategy)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
    }

    const handleDownload = () => {
        if (!strategy) return
        const date = new Date().toISOString().slice(0, 10)   // YYYY-MM-DD
        downloadDOCX({
            content:    strategy,
            case_title: `Litigation_Strategy_${date}`,
        })
    }

    const handleNewSearch = () => {
        abortRef.current?.abort()   // cancel any in-flight stream
        setQuery("")
        setResults(null)
        setStrategy("")
        setError("")
        setShowCases(false)
        setIsReopened(false)
        setStatusMsg("")
        setCopied(false)
        onClearReopen?.()           // notify dashboard to clear reopenedSearch
    }

    // Hydrate from history when initialData changes
    useEffect(() => {
        if (!initialData) return
        setQuery(initialData.query || "")
        setResults(initialData.cases?.length ? initialData.cases : null)
        setStrategy(initialData.strategy || "")
        setShowCases(true)
        setError("")
        setIsReopened(true)
    }, [initialData])

    const clearReopen = () => {
        setResults(null)
        setStrategy("")
        setQuery("")
        setShowCases(false)
        setIsReopened(false)
        onClearReopen?.()
    }

    const handleSearch = async (e) => {
        e.preventDefault()
        if (!query.trim()) return

        // Cancel any previous in-flight request
        abortRef.current?.abort()
        const controller = new AbortController()
        abortRef.current = controller

        setLoading(true)
        setError("")
        setResults(null)
        setStrategy("")
        setShowCases(false)
        setIsReopened(false)
        setStatusMsg("Connecting...")

        try {
            const token = getToken()
            const res = await fetch(`${API}/lawyer/similar-cases-stream`, {
                method:  "POST",
                headers: {
                    "Content-Type":  "application/json",
                    "Authorization": `Bearer ${getToken()}`,
                },
                body:   JSON.stringify({ query, k, include_strategy: true }),
                signal: controller.signal,
            })

            if (!res.ok) {
                const text = await res.text()
                throw new Error(`Server error ${res.status}: ${text}`)
            }

            const reader = res.body.getReader()
            const decoder = new TextDecoder()
            let buffer = ""

            while (true) {
                const { done, value } = await reader.read()
                if (done) break

                buffer += decoder.decode(value, { stream: true })
                const lines = buffer.split("\n\n")
                buffer = lines.pop() // keep incomplete last chunk

                for (const line of lines) {
                    if (!line.startsWith("data: ")) continue
                    try {
                        const payload = JSON.parse(line.slice(6))
                        if (payload.type === "status") {
                            setStatusMsg(payload.message)
                        } else if (payload.type === "result") {
                            setResults(payload.cases || [])
                            setStrategy(payload.strategy || "")
                            setStatusMsg("")
                            setLoading(false)
                        } else if (payload.type === "error") {
                            throw new Error(payload.message)
                        }
                    } catch (parseErr) {
                        // Ignore malformed SSE lines
                    }
                }
            }
        } catch (err) {
            if (err.name === "AbortError") return  // user navigated away
            setError(err.message)
            setLoading(false)
            setStatusMsg("")
        }
    }

    return (
        <div>
            <h2 className="text-xl font-bold text-white mb-2">🔍 Case Similarity Search</h2>
            <p className="text-gray-400 text-sm mb-6">
                Describe your case. AI will analyze it to provide a litigation strategy and research supporting precedents.
            </p>

            <form onSubmit={handleSearch} className="card p-6 space-y-4 mb-8">
                <div>
                    <label className="block text-sm text-gray-400 mb-2">Describe your legal case</label>
                    <textarea
                        value={query}
                        onChange={e => setQuery(e.target.value)}
                        placeholder="e.g. My client is accused of robbery under IPC 392. Fir states gold chain snatching. Need similar acquittals..."
                        rows={4}
                        required
                        className="input-gold resize-none"
                    />
                </div>
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                        <label className="text-sm text-gray-400">Top results:</label>
                        <select value={k} onChange={e => setK(Number(e.target.value))} className="bg-surfaceLight border border-border text-white rounded-lg px-3 py-1.5 text-sm">
                            {[3, 5, 8, 10].map(n => <option key={n} value={n}>{n}</option>)}
                        </select>
                    </div>
                    <button type="submit" disabled={loading || !query.trim()} className="btn-gold flex items-center gap-2 ml-auto px-6">
                        {loading ? (
                            <>
                                <div className="spinner-gold" />
                                <span className="text-sm truncate max-w-[200px]">{statusMsg || "Searching…"}</span>
                            </>
                        ) : "🔍 Generate Strategy"}
                    </button>
                </div>
                {error && <div className="bg-red-500/10 border border-red-400/30 rounded-xl px-4 py-3 text-red-400 text-sm">{error}</div>}
            </form>

            {/* Strategy / results panel */}
            {(strategy || (isReopened && results)) && (
                <div className="space-y-6">
                    {/* Reopened banner */}
                    {isReopened && (
                        <div className="flex items-center justify-between bg-gold/5 border border-gold/20 rounded-xl px-4 py-2.5">
                            <span className="text-gold/80 text-xs font-semibold tracking-wide">↩ Reopened from Search History</span>
                            <button
                                onClick={clearReopen}
                                className="text-xs text-gray-400 hover:text-white transition-colors flex items-center gap-1.5 px-3 py-1 rounded-lg border border-border hover:border-gold/30"
                            >
                                ✕ New Search
                            </button>
                        </div>
                    )}

                    {strategy ? (
                        <div className="card-gold p-8 border-gold/40 animate-fadeIn">
                            <div className="flex justify-between items-center mb-6 border-b border-gold/20 pb-4 flex-wrap gap-3">
                                <h3 className="text-gold font-bold text-lg">🧠 AI Advanced Litigation Strategy</h3>
                                {/* Action buttons — Copy, Download, New Search, toggle cases */}
                                <div className="flex items-center gap-2 flex-wrap">
                                    <button
                                        onClick={handleCopy}
                                        className="btn-glass px-3 py-1.5 text-xs flex items-center gap-1.5"
                                        title="Copy strategy text to clipboard"
                                    >
                                        {copied ? "✅ Copied!" : "📋 Copy"}
                                    </button>
                                    <button
                                        onClick={handleDownload}
                                        className="btn-gold px-3 py-1.5 text-xs flex items-center gap-1.5 hover:scale-105 transition-transform"
                                        title="Download as editable .docx"
                                    >
                                        ⬇️ Download DOCX
                                    </button>
                                    <button
                                        onClick={handleNewSearch}
                                        className="px-3 py-1.5 text-xs rounded-lg border border-border text-gray-400 hover:text-white hover:border-gold/30 transition-all flex items-center gap-1.5"
                                        title="Clear and start a new search"
                                    >
                                        🔄 New Search
                                    </button>
                                    {results && (
                                        <button
                                            onClick={() => setShowCases(!showCases)}
                                            className="text-xs text-gray-400 hover:text-gold transition-colors flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border hover:border-gold/30"
                                        >
                                            {showCases ? "Hide Precedents ▲" : `View ${results.length} Supporting Cases ▼`}
                                        </button>
                                    )}
                                </div>
                            </div>
                            <div className="prose prose-invert prose-sm max-w-none text-gray-200 leading-relaxed space-y-4">
                                <ReactMarkdown>{strategy}</ReactMarkdown>
                            </div>
                        </div>
                    ) : isReopened && (
                        <div className="flex items-center gap-3 bg-surfaceLight border border-border rounded-xl px-4 py-3">
                            <span className="text-gray-500 text-lg">ℹ️</span>
                            <p className="text-gray-400 text-sm">Strategy text wasn't saved for this search. Only case results are available.</p>
                        </div>
                    )}

                    {/* Cases grid */}
                    {(showCases || (isReopened && !strategy)) && results && (
                        <div className="animate-slideDown">
                            <h3 className="text-white font-semibold mb-4 flex items-center gap-2 px-1">
                                📊 Supporting Case Precedents
                            </h3>
                            <div className="grid md:grid-cols-2 gap-4 mb-8">
                                {results.map((c, i) => <CaseCard key={i} c={c} index={i} />)}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {!strategy && !results && !loading && (
                <div className="text-center py-16 text-gray-600">
                    <div className="text-5xl mb-4 opacity-50">🏛️</div>
                    <p>Enter your case details above to generate a professional litigation strategy.</p>
                </div>
            )}
        </div>
    )
}
