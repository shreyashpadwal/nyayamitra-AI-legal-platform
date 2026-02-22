import { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import MessageBubble from './MessageBubble'
import SourceCard from './SourceCard'

const SAMPLE_QUESTIONS = [
  "What are my rights if police arrest me?",
  "How do I file an RTI application?",
  "What is the punishment for theft in IPC?",
  "What to do if a product I bought is defective?",
  "What are Fundamental Rights in Indian Constitution?",
  "Can I get bail for any crime?"
]

const API_BASE = "http://localhost:8000"

// ✅ CHANGE 1: Welcome message now uses proper markdown syntax
// Why: ReactMarkdown renders "- item" as bullets, not "• item"
// The old message used \n\n• which showed as raw text with the old renderer
const WELCOME_MESSAGE = `Namaste! 🙏 I'm your **Indian Legal Assistant**. I can help you understand:

- Indian Constitution & Fundamental Rights
- Indian Penal Code (IPC)
- RTI Act 2005
- Consumer Protection Act 2019
- Code of Criminal Procedure (CrPC)

Ask me any legal question in plain English!`

export default function ChatWindow() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: WELCOME_MESSAGE,
      sources: []
    }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const sendMessage = async (questionOverride) => {
    const question = (questionOverride || input).trim()
    if (!question || loading) return

    const userMsg = { role: 'user', content: question, sources: [] }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const res = await axios.post(`${API_BASE}/ask`, { question })
      const assistantMsg = {
        role: 'assistant',
        content: res.data.answer,
        sources: res.data.sources || []
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch (err) {
      const errorMsg = {
        role: 'assistant',
        // ✅ CHANGE 2: Error message also uses markdown lists now
        content: err.response?.status === 400
          ? `❌ ${err.response.data.detail}`
          : `❌ Could not connect to the backend server.\n\nPlease make sure:\n- Backend is running: \`uvicorn main:app --reload\`\n- It is on port 8000`,
        sources: []
      }
      setMessages(prev => [...prev, errorMsg])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  // ✅ CHANGE 3: Auto-grow textarea based on content
  // Why: Single-line textarea feels cramped for legal questions.
  // This grows up to 120px then scrolls — much better UX.
  const handleInput = (e) => {
    setInput(e.target.value)
    e.target.style.height = 'auto'
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

      {/* Sample question chips */}
      <div style={{
        padding: '10px 20px',
        background: '#13151f',
        borderBottom: '1px solid #1e2235',
        display: 'flex',
        gap: '8px',
        flexWrap: 'wrap'
      }}>
        <span style={{ fontSize: '11px', color: '#6b7280', display: 'flex', alignItems: 'center' }}>Try asking:</span>
        {SAMPLE_QUESTIONS.map((q, i) => (
          <button
            key={i}
            onClick={() => sendMessage(q)}
            disabled={loading}
            style={{
              background: '#1e2235',
              border: '1px solid #2d3250',
              color: '#9ca3af',
              padding: '5px 12px',
              borderRadius: '20px',
              fontSize: '11px',
              cursor: loading ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s',
              whiteSpace: 'nowrap'
            }}
            onMouseOver={e => !loading && (e.target.style.color = '#7c83f5')}
            onMouseOut={e => (e.target.style.color = '#9ca3af')}
          >
            {q}
          </button>
        ))}
      </div>

      {/* Messages area */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '20px'
      }}>
        {messages.map((msg, i) => (
          <div key={i}>
            <MessageBubble role={msg.role} content={msg.content} />
            {msg.sources?.length > 0 && (
              <div style={{
                marginTop: '10px',
                marginLeft: msg.role === 'user' ? 'auto' : '46px',
                maxWidth: msg.role === 'user' ? '75%' : '80%'
              }}>
                <p style={{ fontSize: '11px', color: '#6b7280', marginBottom: '8px', letterSpacing: '0.5px' }}>
                  📚 RETRIEVED SOURCES ({msg.sources.length})
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {msg.sources.map((src, j) => <SourceCard key={j} source={src} />)}
                </div>
              </div>
            )}
          </div>
        ))}

        {/* Loading animation */}
        {loading && (
          <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
            <div style={{
              width: '36px', height: '36px', borderRadius: '50%',
              background: '#2d3250', display: 'flex', alignItems: 'center',
              justifyContent: 'center', fontSize: '18px', flexShrink: 0
            }}>⚖️</div>
            <div style={{
              background: '#1a1d2e', padding: '14px 18px', borderRadius: '18px 18px 18px 4px',
              border: '1px solid #2d3250', display: 'flex', gap: '6px', alignItems: 'center'
            }}>
              <span style={{ fontSize: '12px', color: '#6b7280', marginRight: '8px' }}>Searching legal database...</span>
              {[0, 1, 2].map(i => (
                <div key={i} style={{
                  width: '7px', height: '7px', borderRadius: '50%', background: '#7c83f5',
                  animation: 'pulse 1.2s infinite ease-in-out',
                  animationDelay: `${i * 0.2}s`
                }} />
              ))}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div style={{
        padding: '16px 20px',
        background: '#1a1d2e',
        borderTop: '1px solid #2d3250',
        display: 'flex',
        gap: '12px',
        alignItems: 'flex-end'
      }}>
        <textarea
          value={input}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder="Ask about Indian laws... Press Enter to send, Shift+Enter for new line"
          rows={1}
          style={{
            flex: 1,
            background: '#0f1117',
            border: '1px solid #2d3250',
            color: '#e8e8e8',
            padding: '12px 16px',
            borderRadius: '10px',
            fontSize: '14px',
            outline: 'none',
            resize: 'none',
            fontFamily: 'inherit',
            lineHeight: '1.5',
            maxHeight: '120px',
            overflowY: 'auto',
            transition: 'border-color 0.2s'
          }}
          onFocus={e => e.target.style.borderColor = '#4d54b5'}
          onBlur={e => e.target.style.borderColor = '#2d3250'}
        />
        <button
          onClick={() => sendMessage()}
          disabled={loading || !input.trim()}
          style={{
            background: loading || !input.trim() ? '#2d3250' : '#7c83f5',
            color: 'white',
            border: 'none',
            padding: '12px 22px',
            borderRadius: '10px',
            cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
            fontWeight: '600',
            fontSize: '14px',
            transition: 'background 0.2s',
            whiteSpace: 'nowrap',
            flexShrink: 0
          }}
        >
          {loading ? '...' : 'Ask →'}
        </button>
      </div>

      <div style={{ padding: '8px 20px', background: '#0f1117', textAlign: 'center' }}>
        <p style={{ fontSize: '10px', color: '#374151' }}>
          ⚠️ For informational purposes only. Not a substitute for professional legal advice.
        </p>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 0.3; transform: scale(0.8); }
          50% { opacity: 1; transform: scale(1.2); }
        }
      `}</style>
    </div>
  )
}