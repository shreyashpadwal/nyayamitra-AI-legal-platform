import { useState } from "react"
import { apiPost } from "../utils/auth"
import { downloadDOCX } from "../utils/documents"

const DOC_TYPES = [
    { id: "bail", label: "Bail Application", icon: "🔓", color: "from-blue-500/20 to-blue-600/5", border: "border-blue-500/30" },
    { id: "legal_notice", label: "Legal Notice", icon: "✉️", color: "from-amber-500/20 to-amber-600/5", border: "border-amber-500/30" },
    { id: "written_arguments", label: "Written Arguments", icon: "📝", color: "from-emerald-500/20 to-emerald-600/5", border: "border-emerald-500/30" }
]

export default function LawyerDocumentGenerator() {
    const [activeType, setActiveType] = useState(null)
    const [formData, setFormData] = useState({ case_title: "", details: "" })
    const [generating, setGenerating] = useState(false)
    const [result, setResult] = useState(null)

    const handleGenerate = async (e) => {
        e.preventDefault()
        setGenerating(true)
        setResult(null)
        try {
            const endpoint = `/lawyer/documents/generate-${activeType.replace("_", "-")}`
            const data = await apiPost(endpoint, formData)
            setResult(data)
        } catch (err) {
            alert("Generation failed: " + err.message)
        } finally {
            setGenerating(false)
        }
    }

    const closePreview = () => setResult(null)

    return (
        <div className="max-w-7xl mx-auto space-y-8 animate-fadeIn pb-20">
            <header className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h2 className="text-3xl font-bold text-white tracking-tight">📂 Litigation Document Generator</h2>
                    <p className="text-gray-400 text-sm mt-1">Select a document type to generate professional court-ready drafts.</p>
                </div>
            </header>

            {/* Selection Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {DOC_TYPES.map(type => (
                    <button
                        key={type.id}
                        onClick={() => { setActiveType(type.id); setResult(null); setFormData({ case_title: "", details: "" }) }}
                        className={`group relative overflow-hidden card p-5 text-left transition-all duration-300 hover:scale-[1.02] border-2 ${activeType === type.id ? "border-gold bg-gold/5 shadow-goldglow" : "border-transparent hover:border-gold/30"}`}
                    >
                        <div className="flex items-center gap-4">
                            <div className="text-4xl bg-surfaceLight w-16 h-16 rounded-2xl flex items-center justify-center group-hover:bg-gold/10 transition-colors shadow-inner">
                                {type.icon}
                            </div>
                            <div>
                                <h3 className="text-white font-bold text-base leading-tight">{type.label}</h3>
                                <p className="text-gray-500 text-[10px] uppercase mt-1 tracking-widest font-semibold flex items-center gap-1">
                                    <span className="w-1.5 h-1.5 rounded-full bg-gold/50"></span> Interactive Template
                                </p>
                            </div>
                        </div>
                    </button>
                ))}
            </div>

            {/* Two-column when result exists; full-width form otherwise */}
            <div className={`flex flex-col ${result ? "xl:flex-row" : ""} gap-8 items-start`}>

                {/* Left Side: Form — full-width when no result, 45% when preview is open */}
                <div className={`${result ? "w-full xl:w-[45%]" : "w-full"} space-y-8`}>
                    {activeType ? (
                        <div className="card p-6 border-gold/20 bg-surface/80 backdrop-blur-md shadow-2xl animate-slideInLeft">
                            <div className="flex items-center justify-between mb-6 pb-4 border-b border-border">
                                <h3 className="text-gold font-bold text-lg flex items-center gap-2">
                                    🖋️ Create {DOC_TYPES.find(t => t.id === activeType)?.label}
                                </h3>
                                <div className="text-[10px] text-gray-500 bg-surfaceLight px-2 py-1 rounded-full border border-border">
                                    AI-POWERED DRAFTING
                                </div>
                            </div>
                            <form onSubmit={handleGenerate} className="space-y-6">
                                <div>
                                    <label className="text-[11px] text-gray-400 uppercase tracking-widest mb-2 block font-bold">Case Title / Reference</label>
                                    <input
                                        required
                                        value={formData.case_title}
                                        onChange={e => setFormData({ ...formData, case_title: e.target.value })}
                                        placeholder="e.g. State vs. John Doe - FIR No. 112/2024"
                                        className="input-gold text-sm py-3 px-4 bg-bg/50"
                                    />
                                </div>
                                <div>
                                    <label className="text-[11px] text-gray-400 uppercase tracking-widest mb-2 block font-bold">Case Details &amp; Specific Facts</label>
                                    <textarea
                                        required
                                        rows={10}
                                        value={formData.details}
                                        onChange={e => setFormData({ ...formData, details: e.target.value })}
                                        placeholder={`Enter case facts, prayer details, or specific requirements for the ${activeType.replace("_", " ")}...`}
                                        className="input-gold text-sm py-4 px-4 bg-bg/50 resize-none h-48 leading-relaxed"
                                    />
                                </div>
                                <button type="submit" disabled={generating} className="btn-gold w-full py-4 text-base shadow-goldglow hover:shadow-goldglow-lg transition-all active:scale-[0.98]">
                                    {generating ? <span className="flex items-center justify-center gap-2"><div className="spinner-gold !border-black" /> Generating Document...</span> : "🚀 Craft Professional Draft"}
                                </button>
                            </form>
                        </div>
                    ) : (
                        <div className="card p-16 text-center border-dashed border-gray-800 text-gray-500 bg-surface/30">
                            <div className="text-6xl mb-6 opacity-10">📜</div>
                            <h4 className="text-lg font-medium text-gray-400">Ready to draft?</h4>
                            <p className="text-sm mt-2 max-w-sm mx-auto">Select a document type from the cards above to start generating a professional legal draft.</p>
                        </div>
                    )}
                </div>

                {/* Right Side: Result Preview — only rendered once a document is generated */}
                {result && (
                    <div className="w-full xl:w-[55%] min-h-[500px]">
                        <div className="card p-0 border-gold shadow-goldglow-lg overflow-hidden flex flex-col h-full sticky top-8 animate-fadeIn">
                            {/* Panel header */}
                            <div className="p-5 bg-gold/10 border-b border-gold/20 flex justify-between items-center backdrop-blur-sm">
                                <div>
                                    <h4 className="text-gold font-bold text-sm tracking-wide">{result.case_title}</h4>
                                    <div className="flex items-center gap-2 mt-0.5">
                                        <span className="text-[10px] text-gold/60 uppercase font-black tracking-widest">{result.document_type.replace("_", " ")}</span>
                                        <span className="w-1 h-1 rounded-full bg-gold/30"></span>
                                        <span className="text-[10px] text-gold/40">FINAL AI-GENERATED DRAFT</span>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3">
                                    <button
                                        onClick={() => { navigator.clipboard.writeText(result.content); alert("Copied to clipboard!") }}
                                        className="btn-glass px-4 py-2"
                                    >
                                        📋 Copy
                                    </button>
                                    <button
                                        onClick={() => downloadDOCX(result)}
                                        className="btn-gold px-4 py-2 hover:scale-105"
                                        title="Download editable DOCX"
                                    >
                                        ⬇️ Download DOCX
                                    </button>
                                    {/* Close / back to form */}
                                    <button
                                        onClick={closePreview}
                                        className="w-8 h-8 flex items-center justify-center rounded-lg bg-surfaceLight hover:bg-red-500/20 text-gray-400 hover:text-red-400 transition-colors"
                                        title="Close preview"
                                    >
                                        ✕
                                    </button>
                                </div>
                            </div>
                            {/* Verification warning banner */}
                            {result.verification?.has_unverified && (
                                <div className="mx-5 mt-4 mb-0 flex items-start gap-3 bg-amber-500/10 border border-amber-400/40 rounded-xl px-4 py-3">
                                    <span className="text-amber-400 text-lg mt-0.5 shrink-0">⚠️</span>
                                    <div>
                                        <p className="text-amber-300 text-sm font-semibold mb-1">
                                            Some legal references could not be verified
                                        </p>
                                        <p className="text-amber-200/80 text-xs leading-relaxed">
                                            The following references were not confirmed against our legal database.
                                            Please review them with a lawyer or official source before filing:
                                        </p>
                                        <ul className="mt-2 space-y-0.5">
                                            {result.verification.unverified_citations.map((cite, i) => (
                                                <li key={i} className="text-amber-300 text-xs font-mono bg-amber-500/10 rounded px-2 py-0.5 inline-block mr-1 mb-1">
                                                    {cite}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                </div>
                            )}
                            {/* Document body */}
                            <div className="flex-1 p-12 bg-white text-black overflow-y-auto font-serif text-base leading-[1.8] whitespace-pre-wrap selection:bg-gold/30">
                                <div className="max-w-[700px] mx-auto shadow-sm">
                                    {result.content}
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
