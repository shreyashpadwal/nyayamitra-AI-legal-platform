import { useState, useEffect } from "react"
import { apiGet, apiDelete } from "../utils/auth"
import { downloadDOCX } from "../utils/documents"

export default function LawyerSavedDocuments() {
    const [docs, setDocs] = useState([])
    const [loadingHistory, setLoadingHistory] = useState(true)
    const [selectedDoc, setSelectedDoc] = useState(null)
    const [deleting, setDeleting] = useState(null) // id currently being deleted

    useEffect(() => {
        fetchHistory()
    }, [])

    const fetchHistory = async () => {
        setLoadingHistory(true)
        try {
            const data = await apiGet("/lawyer/documents")
            setDocs(data)
        } catch (err) {
            console.error("Failed to fetch documents", err)
        } finally {
            setLoadingHistory(false)
        }
    }

    const openPreview = (doc) => {
        setSelectedDoc(doc)
        window.scrollTo({ top: 0, behavior: "smooth" })
    }

    const closePreview = () => setSelectedDoc(null)

    const handleDelete = async (doc, e) => {
        e.stopPropagation()
        if (!window.confirm(`Delete "${doc.case_title}"? This cannot be undone.`)) return
        setDeleting(doc.id)
        try {
            await apiDelete(`/lawyer/documents/${doc.id}`)
            setDocs(prev => prev.filter(d => d.id !== doc.id))
            // Close preview panel if the deleted doc was open
            if (selectedDoc?.id === doc.id) closePreview()
        } catch (err) {
            alert("Delete failed: " + err.message)
        } finally {
            setDeleting(null)
        }
    }

    return (
        <div className="max-w-7xl mx-auto space-y-8 animate-fadeIn pb-20">
            <header className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h2 className="text-3xl font-bold text-white tracking-tight">💾 Saved Documents</h2>
                    <p className="text-gray-400 text-sm mt-1">All your previously generated litigation drafts, ready to view or download.</p>
                </div>
                <button onClick={fetchHistory} className="text-[10px] text-gold hover:underline self-start md:self-center">
                    REFRESH
                </button>
            </header>

            {/* Two-column when a doc is selected; full-width list otherwise */}
            <div className={`flex flex-col ${selectedDoc ? "xl:flex-row" : ""} gap-8 items-start`}>

                {/* History List — full-width when nothing selected, 45% when preview is open */}
                <div className={selectedDoc ? "w-full xl:w-[45%]" : "w-full"}>
                    <div className="card p-6 bg-surface/50 border-border/50">
                        <div className="flex items-center justify-between mb-6">
                            <h3 className="text-white font-bold flex items-center gap-2">
                                📂 History &amp; Recent Saved Drafts
                            </h3>
                        </div>
                        {loadingHistory ? (
                            <div className="flex justify-center p-8"><div className="spinner-gold" /></div>
                        ) : docs.length > 0 ? (
                            <div className="grid grid-cols-1 gap-3 max-h-[600px] overflow-y-auto pr-2 custom-scrollbar">
                                {docs.map(doc => (
                                    <div
                                        key={doc.id}
                                        className={`p-4 bg-bg/40 border rounded-xl flex items-center justify-between transition-all group hover:bg-surfaceLight/30 ${selectedDoc?.id === doc.id ? "border-gold/60 bg-gold/5" : "border-border/50 hover:border-gold/40"}`}
                                    >
                                        <div className="min-w-0 flex-1 pr-4">
                                            <div className="text-white font-semibold text-sm truncate group-hover:text-gold transition-colors">{doc.case_title}</div>
                                            <div className="text-[10px] text-gray-500 uppercase flex items-center gap-2 mt-1">
                                                <span className={`px-2 py-0.5 rounded ${doc.document_type === "bail" ? "bg-blue-500/10 text-blue-400" : doc.document_type === "legal_notice" ? "bg-amber-500/10 text-amber-400" : "bg-emerald-500/10 text-emerald-400"}`}>
                                                    {doc.document_type.replace("_", " ")}
                                                </span>
                                                <span className="opacity-30">•</span>
                                                <span>{new Date(doc.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}</span>
                                            </div>
                                        </div>
                                        <div className="flex gap-2">
                                            {/* View */}
                                            <button
                                                onClick={() => openPreview(doc)}
                                                className={`w-8 h-8 flex items-center justify-center rounded-lg transition-colors ${selectedDoc?.id === doc.id ? "bg-gold/20 text-gold" : "bg-surfaceLight hover:bg-gold/20 text-gold"}`}
                                                title="View"
                                            >
                                                👁️
                                            </button>
                                            {/* Download */}
                                            <button
                                                onClick={() => downloadDOCX(doc)}
                                                className="w-8 h-8 flex items-center justify-center bg-surfaceLight hover:bg-gold/20 text-gold rounded-lg transition-colors"
                                                title="Download DOCX"
                                            >
                                                ⬇️
                                            </button>
                                            {/* Delete */}
                                            <button
                                                onClick={(e) => handleDelete(doc, e)}
                                                disabled={deleting === doc.id}
                                                className="w-8 h-8 flex items-center justify-center rounded-lg bg-transparent hover:bg-red-500/20 text-gray-600 hover:text-red-400 transition-colors disabled:opacity-40"
                                                title="Delete draft"
                                            >
                                                {deleting === doc.id
                                                    ? <div className="spinner-gold w-3 h-3 !border-red-400" />
                                                    : "🗑"}
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-center py-12 text-gray-600">
                                <p className="text-sm italic">No history found.</p>
                                <p className="text-[10px] mt-1 uppercase tracking-widest">Everything you generate will appear here</p>
                            </div>
                        )}
                    </div>
                </div>

                {/* Right Side: Document Preview — only rendered when a doc is selected */}
                {selectedDoc && (
                    <div className="w-full xl:w-[55%] min-h-[500px]">
                        <div className="card p-0 border-gold shadow-goldglow-lg overflow-hidden flex flex-col h-full sticky top-8 animate-fadeIn">
                            {/* Panel header */}
                            <div className="p-5 bg-gold/10 border-b border-gold/20 flex justify-between items-center backdrop-blur-sm">
                                <div>
                                    <h4 className="text-gold font-bold text-sm tracking-wide">{selectedDoc.case_title}</h4>
                                    <div className="flex items-center gap-2 mt-0.5">
                                        <span className="text-[10px] text-gold/60 uppercase font-black tracking-widest">{selectedDoc.document_type.replace("_", " ")}</span>
                                        <span className="w-1 h-1 rounded-full bg-gold/30"></span>
                                        <span className="text-[10px] text-gold/40">SAVED DRAFT</span>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3">
                                    <button
                                        onClick={() => { navigator.clipboard.writeText(selectedDoc.content); alert("Copied to clipboard!") }}
                                        className="btn-glass px-4 py-2"
                                    >
                                        📋 Copy
                                    </button>
                                    <button
                                        onClick={() => downloadDOCX(selectedDoc)}
                                        className="btn-gold px-4 py-2 hover:scale-105"
                                        title="Download editable DOCX"
                                    >
                                        ⬇️ Download DOCX
                                    </button>
                                    {/* Close / back button */}
                                    <button
                                        onClick={closePreview}
                                        className="w-8 h-8 flex items-center justify-center rounded-lg bg-surfaceLight hover:bg-red-500/20 text-gray-400 hover:text-red-400 transition-colors"
                                        title="Close preview"
                                    >
                                        ✕
                                    </button>
                                </div>
                            </div>
                            {/* Document body */}
                            <div className="flex-1 p-12 bg-white text-black overflow-y-auto font-serif text-base leading-[1.8] whitespace-pre-wrap selection:bg-gold/30">
                                <div className="max-w-[700px] mx-auto shadow-sm">
                                    {selectedDoc.content}
                                </div>
                            </div>
                            <div className="p-4 bg-gray-50 border-t border-gray-200 text-center text-gray-400 text-[10px] uppercase font-bold tracking-widest">
                                Private &amp; Confidential • Prepared for Legal Consultation
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}
