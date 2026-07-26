import { useState, useRef, useEffect } from "react"
import { useNavigate, useLocation } from "react-router-dom"
import { clearSession, API, authHeaders } from "../utils/auth"
import ReactMarkdown from "react-markdown"
import ThemeToggle from "../components/ThemeToggle"

const SUGGESTIONS = [
    "What are Fundamental Rights in the Indian Constitution?",
    "How do I file an RTI application?",
    "What is the punishment for theft in IPC?",
    "What to do if a product I bought is defective?",
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
            <div className={`max-w-[78%] rounded-2xl px-4 py-3 text-sm leading-relaxed
                ${isUser
                    ? "bg-primary text-white rounded-tr-sm"
                    : "bg-surfaceLight text-gray-200 rounded-tl-sm border border-border"
                }`}>
                {msg.error ? (
                    <div className="flex items-center gap-2 text-red-400">
                        <span>⚠️</span>
                        <span>{msg.error}</span>
                    </div>
                ) : (
                    <div className={!isUser ? "prose-legal" : ""}>
                        <ReactMarkdown
                            components={{
                                strong: ({children}) => <strong className="font-semibold text-white">{children}</strong>,
                                p: ({children}) => <p className="mb-2 last:mb-0">{children}</p>,
                                ul: ({children}) => <ul className="list-none space-y-1 my-2">{children}</ul>,
                                li: ({children}) => (
                                    <li className="flex gap-2">
                                        <span className="text-primary mt-0.5 flex-shrink-0 text-xs">▸</span>
                                        <span>{children}</span>
                                    </li>
                                ),
                                ol: ({children}) => <ol className="list-decimal list-inside space-y-1 my-2 pl-2">{children}</ol>,
                            }}
                        >
                            {msg.content}
                        </ReactMarkdown>
                    </div>
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
    const [statusMessage, setStatusMessage] = useState("")
    const bottomRef = useRef(null)
    const isSendingRef = useRef(false)   // synchronous guard — immune to state-batching race
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
    }, [messages, statusMessage])

    const sendMessage = async (question) => {
        const q = question || input.trim()
        if (!q || isSendingRef.current) return   // synchronous check beats React state batching
        isSendingRef.current = true               // lock before any await
        setInput("")
        setMessages(prev => [...prev, { role: "user", content: q, sources: [] }])
        setLoading(true)
        setStatusMessage("Connecting to legal engine...")

        // Build last 2 completed Q&A turns for conversational context.
        // Walk messages in order, pairing user messages with the next non-loading assistant reply.
        const completedTurns = []
        const prevMsgs = messages  // snapshot before state update
        for (let i = 0; i < prevMsgs.length - 1; i++) {
            const m = prevMsgs[i]
            const next = prevMsgs[i + 1]
            if (
                m.role === "user" &&
                next?.role === "assistant" &&
                next.content &&
                !next.loading &&
                !next.error
            ) {
                completedTurns.push({ question: m.content, answer: next.content })
                i++ // skip the assistant message we just consumed
            }
        }
        const history = completedTurns.slice(-2)  // last 2 turns only

        try {
            // Use the SSE streaming endpoint for live pipeline status.
            // Parses SSE manually (EventSource doesn't support POST + auth headers).
            const res = await fetch(`${API}/citizen/ask-stream`, {
                method: "POST",
                headers: authHeaders(),
                body: JSON.stringify({ question: q, history }),
            })

            if (!res.ok) {
                const errBody = await res.json().catch(() => ({ detail: "Request failed" }))
                throw new Error(errBody.detail || "Request failed")
            }

            const reader = res.body.getReader()
            const decoder = new TextDecoder()
            let buffer = ""
            let answered = false

            while (true) {
                const { done, value } = await reader.read()
                if (done) break

                buffer += decoder.decode(value, { stream: true })

                // SSE events are delimited by double newlines
                const parts = buffer.split("\n\n")
                buffer = parts.pop() ?? ""   // keep the incomplete trailing chunk

                for (const part of parts) {
                    const line = part.trim()
                    if (!line.startsWith("data: ")) continue
                    try {
                        const event = JSON.parse(line.slice(6))
                        if (event.type === "status") {
                            setStatusMessage(event.message)
                        } else if (event.type === "final") {
                            setMessages(prev => [...prev, {
                                role: "assistant",
                                content: event.answer,
                                sources: event.sources || [],
                            }])
                            setStatusMessage("")
                            answered = true
                        } else if (event.type === "error") {
                            throw new Error(event.message)
                        }
                    } catch (_parseErr) {
                        // Ignore malformed SSE lines silently
                    }
                }
            }

            // Graceful fallback: stream closed without a final event
            if (!answered) {
                throw new Error("Stream ended without an answer — please retry.")
            }

        } catch (err) {
            if (err.message?.includes("401")) { clearSession(); navigate("/login") }
            setMessages(prev => [...prev, { role: "assistant", content: null, error: err.message, sources: [] }])
        } finally {
            setLoading(false)
            setStatusMessage("")
            isSendingRef.current = false   // release lock so next message can be sent
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
                <div className="flex items-center gap-3">
                    <ThemeToggle />
                    <div className="w-2.5 h-2.5 bg-green-400 rounded-full animate-pulse" title="Live" />
                </div>
            </header>

            {/* Suggestions */}
            <div className="px-4 py-2.5 border-b border-border overflow-x-auto flex gap-2 flex-shrink-0">
                {SUGGESTIONS.map((s, i) => (
                    <button
                        key={i}
                        onClick={() => sendMessage(s)}
                        disabled={loading}
                        className="flex-shrink-0 bg-surfaceLight border border-border hover:border-primary/40 text-gray-400 hover:text-white px-3 py-1.5 rounded-full text-xs transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed"
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

                    {/* Live pipeline status indicator */}
                    {loading && (
                        <div className="flex gap-3 mb-4">
                            <div className="w-8 h-8 rounded-full bg-surfaceLight border border-border flex items-center justify-center text-sm flex-shrink-0">⚖️</div>
                            <div className="bg-surfaceLight border border-border rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-2.5 min-w-0">
                                {/* Bouncing dots */}
                                <div className="flex gap-1.5 flex-shrink-0">
                                    <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                                    <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                                    <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                                </div>
                                {/* Live status text fades in per stage */}
                                {statusMessage && (
                                    <span className="text-xs text-gray-400 italic truncate transition-all duration-300">
                                        {statusMessage}
                                    </span>
                                )}
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
                        onChange={e => { setInput(e.target.value); e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px" }}
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
