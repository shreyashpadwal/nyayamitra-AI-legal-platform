import ChatWindow from './components/ChatWindow'

function App() {
  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#0f1117' }}>
      <header style={{
        background: '#1a1d2e',
        padding: '16px 24px',
        borderBottom: '1px solid #2d3250',
        display: 'flex',
        alignItems: 'center',
        gap: '14px'
      }}>
        <span style={{ fontSize: '32px' }}>⚖️</span>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: '700', color: '#7c83f5', letterSpacing: '-0.5px' }}>
            Indian Legal Assistant
          </h1>
          <p style={{ fontSize: '12px', color: '#6b7280', marginTop: '2px' }}>
            Powered by RAG • Indian Constitution, IPC, RTI, Consumer Protection Act
          </p>
        </div>
        <div style={{ marginLeft: 'auto', fontSize: '12px', color: '#4ade80', background: '#0d2a1a', padding: '4px 10px', borderRadius: '20px', border: '1px solid #166534' }}>
          🟢 Live
        </div>
      </header>
      <ChatWindow />
    </div>
  )
}

export default App