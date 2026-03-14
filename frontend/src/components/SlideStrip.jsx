/** Thumbnail strip of slides; used in Rehearsal. Preserves aspect ratio (no crop). Optional per-slide "Challenge Me". */
export default function SlideStrip({ slideUrls = [], currentIndex = 0, onSelect, sessionId, onChallengeSlide }) {
  return (
    <div style={{ display: 'flex', gap: 8, overflowX: 'auto', padding: 8 }}>
      {slideUrls.map((url, i) => (
        <div
          key={i}
          style={{
            flexShrink: 0,
            width: 100,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 4,
          }}
        >
          <button
            type="button"
            onClick={() => onSelect?.(i)}
            style={{
              border: i === currentIndex ? '2px solid #3b82f6' : '1px solid #333',
              borderRadius: 4,
              padding: 0,
              width: '100%',
              height: 56,
              background: '#222',
              cursor: 'pointer',
              overflow: 'hidden',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {url ? (
              <img
                src={url}
                alt={`Slide ${i + 1}`}
                style={{ maxWidth: '100%', maxHeight: '100%', width: 'auto', height: 'auto', objectFit: 'contain' }}
              />
            ) : (
              `Slide ${i + 1}`
            )}
          </button>
          {sessionId && onChallengeSlide && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation()
                onChallengeSlide(i)
              }}
              style={{
                fontSize: 10,
                padding: '2px 6px',
                background: '#333',
                color: '#93c5fd',
                border: '1px solid #555',
                borderRadius: 4,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              Challenge Me
            </button>
          )}
        </div>
      ))}
    </div>
  )
}
