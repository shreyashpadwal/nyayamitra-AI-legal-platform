import { useState, useRef, useEffect } from "react"
import { useNavigate, useLocation } from "react-router-dom"
import { apiPost, clearSession } from "../utils/auth"
import ReactMarkdown from "react-markdown"

const SUGGESTIONS = [
    "What are my rights if police arrest me?",
    "How do I file an RTI application?",
    "What is the punishment for theft in IPC?",
    "What to do if a product I bought is defective?",
    "What are Fundamental Rights in the Indian Constitution?",
    "Can I get bail for any crime?",
]

function SourceCard({ source }) {
    return (
        <div className="bg-primary/5 border border-primary/20 rounded-xl px-3 py-2 text-xs">
            <div className="text-primary font-semibold">{source.law}</div>
            <div className="text-gray-500">Page {source.page}</div>
            <div className="text-gray-400 mt-1 line-clamp-2">{source.excerpt}</div>
        </div>
    )
}

function MessageBubble({ msg }) {
    const isUser = msg.role === "user"
    return (
        <div className={`flex gap-3 mb-4 ${isUser ? "flex-row-reverse" : ""}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-sm font-bold
        ${isUser ? "bg-primary" : "bg-surfaceLight border border-border"}`}>
                {isUser ? "U" : "⚖️"}
            </div>
            <div className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed
        ${isUser ? "bg-primary text-white rounded-tr-sm" : "bg-surfaceLight text-gray-200 rounded-tl-sm border border-border"}`}>
                {msg.error ? (
                    <span className="text-red-400">⚠️ {msg.error}</span>
                ) : (
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                )}
            </div>
        </div>
    )
}

export default function ChatPage() {
    const [messages, setMessages] = useState([{
        role: "assistant",
        content: `Namaste! 🙏 I'm your Indian Legal Assistant. I can help you understand:\n\n• **Indian Constitution** & Fundamental Rights\n• **Indian Penal Code (IPC)**\n• **RTI Act 2005**\n• **Consumer Protection Act 2019**\n• **Code of Criminal Procedure (CrPC)**\n\nAsk me any legal question in plain English!`,
        sources: []
    }])
    const [input, setInput] = useState("")
    const [loading, setLoading] = useState(false)
    const bottomRef = useRef(null)
    const navigate = useNavigate()
    const location = useLocation()

    // If navigated with a pre-filled question OR history
    useEffect(() => {
        if (location.state?.historyItem) {
            const item = location.state.historyItem
            setMessages([
                { role: "user", content: item.question },
                { role: "assistant", content: item.answer, sources: [] }
            ])
        } else if (location.state?.question) {
            sendMessage(location.state.question)
        }
    }, [])

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" })
    }, [messages])

    const sendMessage = async (question) => {
        const q = question || input.trim()
        if (!q || loading) return
        setInput("")
        setMessages(prev => [...prev, { role: "user", content: q, sources: [] }])
        setLoading(true)
        try {
            const data = await apiPost("/citizen/ask", { question: q })
            setMessages(prev => [...prev, { role: "assistant", content: data.answer, sources: data.sources || [] }])
        } catch (err) {
            if (err.message.includes("401")) { clearSession(); navigate("/login") }
            setMessages(prev => [...prev, { role: "assistant", content: null, error: err.message, sources: [] }])
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="flex flex-col h-screen bg-bg">
            {/* Header */}
            <header className="bg-surface border-b border-border px-5 py-3.5 flex justify-between items-center flex-shrink-0">
                <div className="flex items-center gap-3">
                    <button onClick={() => navigate("/citizen")} className="text-gray-400 hover:text-white text-sm transition-colors">
                        ← Dashboard
                    </button>
                    <div className="w-8 h-8 bg-primary/20 rounded-full flex items-center justify-center text-lg">⚖️</div>
                    <div>
                        <p className="text-white font-bold text-sm">Indian Legal Assistant</p>
                        <p className="text-gray-500 text-xs">Powered by RAG · FAISS · Groq LLaMA</p>
                    </div>
                </div>
                <div className="w-2.5 h-2.5 bg-green-400 rounded-full animate-pulse" title="Live" />
            </header>

            {/* Suggestions */}
            <div className="px-4 py-2.5 border-b border-border overflow-x-auto flex gap-2 flex-shrink-0">
                {SUGGESTIONS.map((s, i) => (
                    <button
                        key={i}
                        onClick={() => sendMessage(s)}
                        className="flex-shrink-0 bg-surfaceLight border border-border hover:border-primary/40 text-gray-400 hover:text-white px-3 py-1.5 rounded-full text-xs transition-all duration-200"
                    >
                        {s}
                    </button>
                ))}
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-6 py-4">
                <div className="max-w-3xl mx-auto">
                    {messages.map((msg, i) => (
                        <div key={i}>
                            <MessageBubble msg={msg} />
                            {msg.sources?.length > 0 && (
                                <div className="ml-11 mb-4 grid grid-cols-1 sm:grid-cols-3 gap-2">
                                    {msg.sources.map((src, j) => <SourceCard key={j} source={src} />)}
                                </div>
                            )}
                        </div>
                    ))}
                    {loading && (
                        <div className="flex gap-3 mb-4">
                            <div className="w-8 h-8 rounded-full bg-surfaceLight border border-border flex items-center justify-center text-sm">⚖️</div>
                            <div className="bg-surfaceLight border border-border rounded-2xl rounded-tl-sm px-4 py-3 flex gap-1.5 items-center">
                                <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                                <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                                <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                            </div>
                        </div>
                    )}
                    <div ref={bottomRef} />
                </div>
            </div>

            {/* Input */}
            <div className="bg-surface border-t border-border px-4 py-4 flex-shrink-0">
                <div className="max-w-3xl mx-auto flex gap-3">
                    <textarea
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage() } }}
                        placeholder="Ask about Indian law… (Enter to send, Shift+Enter for new line)"
                        rows={1}
                        className="input flex-1 resize-none"
                        style={{ minHeight: "48px", maxHeight: "160px" }}
                    />
                    <button
                        onClick={() => sendMessage()}
                        disabled={loading || !input.trim()}
                        className="btn-primary px-5"
                    >
                        {loading ? <div className="spinner" /> : "→"}
                    </button>
                </div>
            </div>
        </div>
    )
}
