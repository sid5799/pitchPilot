import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useLiveSession } from '../hooks/useLiveSession'
import LiveFeedback from '../components/LiveFeedback'

const SESSION_KEY = 'pitchpilot_session'

function getSlideUrls(sessionId, locationState) {
  if (locationState?.slide_urls?.length) return locationState.slide_urls
  try {
    const raw = sessionStorage.getItem(`${SESSION_KEY}_${sessionId}`)
    if (raw) {
      const data = JSON.parse(raw)
      return data.slide_urls || []
    }
  } catch (_) {}
  return []
}

export default function Challenge() {
  const { sessionId } = useParams()
  const [searchParams] = useSearchParams()
  const scope = searchParams.get('scope') || 'all'
  const indexParam = searchParams.get('index')
  const slideIndex = indexParam !== null ? parseInt(indexParam, 10) : undefined
  const slideUrls = getSlideUrls(sessionId, null)
  const [micActive, setMicActive] = useState(false)

  const wsOptions = useMemo(
    () =>
      scope === 'slide' && typeof slideIndex === 'number' && !Number.isNaN(slideIndex)
        ? { mode: 'challenge', scope: 'slide', slideIndex }
        : { mode: 'challenge', scope: 'all' },
    [scope, slideIndex]
  )

  const {
    connect,
    disconnect,
    startMic,
    stopMic,
    isConnected,
    reconnecting,
    userTranscript,
    agentResponse,
    feedback,
    error,
    goAway,
  } = useLiveSession(sessionId, slideUrls, wsOptions)

  useEffect(() => {
    return () => disconnect()
  }, [disconnect])

  const handleStart = () => connect()
  const handleMicToggle = () => {
    if (micActive) {
      stopMic()
      setMicActive(false)
    } else {
      startMic()
      setMicActive(true)
    }
  }
  const handleStop = () => {
    disconnect()
    setMicActive(false)
  }

  const challengeLabel =
    scope === 'slide' && typeof slideIndex === 'number' && !Number.isNaN(slideIndex)
      ? `Slide ${slideIndex + 1}`
      : 'Full presentation'

  return (
    <div style={{ padding: '2rem', maxWidth: 700, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h1>Challenge Me – {challengeLabel}</h1>
        <span>
          <Link to={`/rehearsal/${sessionId}`} style={{ marginRight: 12 }}>
            Rehearsal
          </Link>
          <Link to="/">Upload</Link>
        </span>
      </div>

      <p style={{ marginBottom: 16, color: '#aaa' }}>
        The agent will ask you Q&A about the selected slide(s). Answer by voice; the agent will evaluate briefly and ask the next question.
      </p>

      {reconnecting && <p style={{ color: '#fbbf24', marginBottom: 8 }}>Reconnecting…</p>}
      {!isConnected && !reconnecting ? (
        <button onClick={handleStart} style={{ padding: '0.5rem 1rem', marginBottom: 16 }}>
          Start challenge
        </button>
      ) : isConnected ? (
        <div style={{ marginBottom: 16 }}>
          <button
            onClick={handleMicToggle}
            style={{
              padding: '0.5rem 1rem',
              marginRight: 8,
              background: micActive ? '#22c55e' : '#444',
              color: '#fff',
              border: 'none',
              borderRadius: 4,
            }}
          >
            {micActive ? 'Mute mic' : 'Start mic'}
          </button>
          <button onClick={handleStop} style={{ padding: '0.5rem 1rem' }}>
            End challenge
          </button>
        </div>
      ) : null}

      {error && !reconnecting && <p style={{ color: '#f87171', marginTop: 8 }}>{error}</p>}
      <LiveFeedback
        userTranscript={userTranscript}
        agentResponse={agentResponse}
        feedback={feedback}
        goAway={goAway}
        groupBySlide={false}
      />
    </div>
  )
}
