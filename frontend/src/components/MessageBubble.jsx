import ReactMarkdown from 'react-markdown'

export default function MessageBubble({ role, content }) {
  const isUser = role === 'user'

  return (
    <div style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
      alignItems: 'flex-start',
      gap: '10px'
    }}>
      {/* Assistant avatar */}
      {!isUser && (
        <div style={{
          width: '36px',
          height: '36px',
          borderRadius: '50%',
          background: 'linear-gradient(135deg, #2d3250, #4d54b5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          fontSize: '18px',
          border: '1px solid #4d54b5'
        }}>⚖️</div>
      )}

      {/* Message bubble */}
      <div style={{
        maxWidth: '75%',
        background: isUser
          ? 'linear-gradient(135deg, #3d4499, #4d54b5)'
          : '#1a1d2e',
        color: '#e8e8e8',
        padding: '14px 18px',
        borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
        fontSize: '14px',
        lineHeight: '1.8',
        border: '1px solid ' + (isUser ? '#5a62cc' : '#2d3250'),
        wordBreak: 'break-word',
        boxShadow: isUser
          ? '0 2px 12px rgba(93, 101, 204, 0.25)'
          : '0 2px 8px rgba(0,0,0,0.2)'
      }}>
        {isUser ? (
          // User messages: plain text is fine
          <span>{content}</span>
        ) : (
          // Assistant messages: render markdown properly
          <ReactMarkdown
            components={{
              // Headings
              h1: ({ children }) => (
                <h1 style={{ fontSize: '16px', fontWeight: '700', margin: '10px 0 6px', color: '#c5c8ff' }}>{children}</h1>
              ),
              h2: ({ children }) => (
                <h2 style={{ fontSize: '15px', fontWeight: '700', margin: '10px 0 6px', color: '#c5c8ff' }}>{children}</h2>
              ),
              h3: ({ children }) => (
                <h3 style={{ fontSize: '14px', fontWeight: '700', margin: '8px 0 4px', color: '#c5c8ff' }}>{children}</h3>
              ),

              // Paragraphs
              p: ({ children }) => (
                <p style={{ margin: '6px 0', lineHeight: '1.8' }}>{children}</p>
              ),

              // Bold text — renders **text** properly
              strong: ({ children }) => (
                <strong style={{ color: '#ffffff', fontWeight: '700' }}>{children}</strong>
              ),

              // Italic text
              em: ({ children }) => (
                <em style={{ color: '#a0a8e8' }}>{children}</em>
              ),

              // Bullet lists
              ul: ({ children }) => (
                <ul style={{ paddingLeft: '18px', margin: '6px 0' }}>{children}</ul>
              ),

              // Numbered lists
              ol: ({ children }) => (
                <ol style={{ paddingLeft: '18px', margin: '6px 0' }}>{children}</ol>
              ),

              // List items
              li: ({ children }) => (
                <li style={{ margin: '4px 0', lineHeight: '1.7' }}>{children}</li>
              ),

              // Horizontal rule (---)
              hr: () => (
                <hr style={{ border: 'none', borderTop: '1px solid #2d3250', margin: '12px 0' }} />
              ),

              // Inline code
              code: ({ children }) => (
                <code style={{
                  background: '#0d0f1a',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  fontSize: '13px',
                  color: '#7eb8f7'
                }}>{children}</code>
              ),

              // Blockquote (for disclaimer styling)
              blockquote: ({ children }) => (
                <blockquote style={{
                  borderLeft: '3px solid #4d54b5',
                  paddingLeft: '10px',
                  margin: '8px 0',
                  color: '#9090b0',
                  fontStyle: 'italic'
                }}>{children}</blockquote>
              ),
            }}
          >
            {content}
          </ReactMarkdown>
        )}
      </div>

      {/* User avatar */}
      {isUser && (
        <div style={{
          width: '36px',
          height: '36px',
          borderRadius: '50%',
          background: 'linear-gradient(135deg, #3d4499, #4d54b5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          fontSize: '16px',
          border: '1px solid #5a62cc'
        }}>👤</div>
      )}
    </div>
  )
}