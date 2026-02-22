export default function SourceCard({ source }) {
  return (
    <div style={{
      background: '#13151f',
      border: '1px solid #2d3250',
      borderLeft: '3px solid #7c83f5',
      borderRadius: '8px',
      padding: '10px 14px',
      transition: 'border-color 0.2s'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
        <span style={{ fontSize: '12px', fontWeight: '600', color: '#7c83f5' }}>
          📄 {source.law}
        </span>
        <span style={{
          fontSize: '10px',
          color: '#6b7280',
          background: '#1e2235',
          padding: '2px 8px',
          borderRadius: '10px',
          border: '1px solid #2d3250'
        }}>
          Page {source.page}
        </span>
      </div>
      <p style={{
        fontSize: '12px',
        color: '#9ca3af',
        lineHeight: '1.6',
        fontStyle: 'italic'
      }}>
        "{source.excerpt}"
      </p>
    </div>
  )
}