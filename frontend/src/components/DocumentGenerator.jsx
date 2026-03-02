import { useState } from "react"
import { apiPost, API } from "../utils/auth"
import ReactMarkdown from "react-markdown"

const DOC_TYPES = [
    { key: "police_complaint", icon: "🚔", title: "Police Complaint", desc: "File a formal complaint with police" },
    { key: "consumer_complaint", icon: "🛒", title: "Consumer Complaint", desc: "Under Consumer Protection Act 2019" },
    { key: "rti_application", icon: "📋", title: "RTI Application", desc: "Right to Information Act 2005" },
]

export default function DocumentGenerator() {
    const [docType, setDocType] = useState("")
    const [desc, setDesc] = useState("")
    const [generated, setGenerated] = useState("")
    const [title, setTitle] = useState("")
    const [draftId, setDraftId] = useState(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState("")

    const handleGenerate = async (e) => {
        e.preventDefault()
        if (!docType) return
        setLoading(true); setError(""); setGenerated("")
        try {
            const data = await apiPost("/citizen/generate-document", {
                doc_type: docType,
                fields: { description: desc }
            })
            setGenerated(data.content)
            setTitle(data.title || "Document")
            setDraftId(data.draft_id)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    const handleCopy = () => {
        navigator.clipboard.writeText(generated)
    }

    const handleDownload = async () => {
        if (!draftId) return
        try {
            const token = localStorage.getItem("legal_token")
            const res = await fetch(`${API}/citizen/download-docx/${draftId}`, {
                headers: { "Authorization": `Bearer ${token}` }
            })
            const blob = await res.blob()
            const url = window.URL.createObjectURL(blob)
            const a = document.createElement("a")
            a.href = url
            a.download = `${title.replace(/\s+/g, '_')}.docx`
            document.body.appendChild(a)
            a.click()
            a.remove()
        } catch (err) {
            console.error("Download failed", err)
        }
    }

    return (
        <div className="max-w-3xl">
            <h2 className="text-xl font-bold text-white mb-2">📄 Document Generator</h2>
            <p className="text-gray-400 text-sm mb-6">AI generates a professional, ready-to-submit legal document from your description.</p>

            {/* Doc type selection */}
            <div className="grid grid-cols-3 gap-3 mb-6">
                {DOC_TYPES.map(d => (
                    <button
                        key={d.key}
                        onClick={() => setDocType(d.key)}
                        className={`p-4 rounded-xl border text-left transition-all duration-200
              ${docType === d.key ? "border-primary/50 bg-primary/10" : "card hover:border-gray-600"}`}
                    >
                        <div className="text-2xl mb-2">{d.icon}</div>
                        <div className="text-white font-semibold text-sm">{d.title}</div>
                        <div className="text-gray-500 text-xs mt-0.5">{d.desc}</div>
                    </button>
                ))}
            </div>

            {docType && (
                <form onSubmit={handleGenerate} className="card p-6 space-y-4">
                    <div>
                        <label className="block text-sm text-gray-400 mb-2">
                            Describe your situation in detail
                        </label>
                        <textarea
                            value={desc}
                            onChange={e => setDesc(e.target.value)}
                            placeholder="Explain what happened, when, where, who was involved, what you want to request or complaint about…"
                            rows={5}
                            required
                            className="input resize-none"
                        />
                        <p className="text-gray-600 text-xs mt-1.5">
                            The more detail you provide, the better the document.
                        </p>
                    </div>

                    {error && (
                        <div className="bg-red-500/10 border border-red-400/30 rounded-xl px-4 py-3 text-red-400 text-sm">
                            {error}
                        </div>
                    )}

                    <button type="submit" disabled={loading || !desc.trim()} className="btn-primary w-full flex items-center justify-center gap-2">
                        {loading
                            ? <><div className="spinner" /> Generating document…</>
                            : "✨ Generate Document"}
                    </button>
                </form>
            )}

            {/* Output */}
            {generated && (
                <div className="mt-6">
                    <div className="flex items-center justify-between mb-3">
                        <h3 className="text-white font-semibold">{title}</h3>
                        <div className="flex gap-2">
                            <button onClick={handleCopy} className="badge-green cursor-pointer hover:opacity-80 transition-opacity px-3 py-1">
                                📋 Copy
                            </button>
                            <button onClick={handleDownload} className="bg-gold/15 text-gold border border-gold/30 px-3 py-1 rounded-full text-xs font-semibold hover:opacity-80 transition-opacity">
                                ⬇️ Download
                            </button>
                        </div>
                    </div>
                    <div className="card p-6 font-mono text-sm text-gray-200 leading-relaxed whitespace-pre-wrap max-h-[500px] overflow-y-auto">
                        {generated}
                    </div>
                    <p className="text-gray-600 text-xs mt-2 text-center">
                        *This document is AI-generated. Please review before submission.*
                    </p>
                </div>
            )}
        </div>
    )
}
