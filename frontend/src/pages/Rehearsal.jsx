import { useEffect, useState } from 'react'
import { Link, useParams, useLocation, useNavigate } from 'react-router-dom'
import { useLiveSession } from '../hooks/useLiveSession'
import SlideStrip from '../components/SlideStrip'
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

export default function Rehearsal() {
  const { sessionId } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const slideUrls = getSlideUrls(sessionId, location.state)
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0)
  const [micActive, setMicActive] = useState(false)

  const {
    connect,
    disconnect,
    startMic,
    stopMic,
    sendSlideIndex,
    isConnected,
    reconnecting,
    userTranscript,
    agentResponse,
    feedback,
    error,
    goAway,
  } = useLiveSession(sessionId, slideUrls)

  useEffect(() => {
    return () => disconnect()
  }, [disconnect])

  useEffect(() => {
    if (isConnected && slideUrls.length && currentSlideIndex >= 0) {
      sendSlideIndex(currentSlideIndex)
    }
  }, [isConnected, currentSlideIndex, slideUrls.length, sendSlideIndex])

  const handleStart = () => {
    connect()
  }

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

  return (
    <div style={{ padding: '2rem', maxWidth: 900, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h1>Rehearsal</h1>
        <span>
          <Link to={`/challenge/${sessionId}?scope=all`} style={{ marginRight: 12 }}>Challenge Me (full)</Link>
          <Link to={`/qna/${sessionId}`} style={{ marginRight: 12 }}>Practice Q&A</Link>
          <Link to="/">Upload new</Link>
        </span>
      </div>

      {slideUrls.length === 0 && (
        <p style={{ color: '#f87171' }}>
          No slides in session. <Link to="/">Upload a presentation</Link> first.
        </p>
      )}

      {slideUrls.length > 0 && (
        <>
          <SlideStrip
            sessionId={sessionId}
            slideUrls={slideUrls}
            currentIndex={currentSlideIndex}
            onSelect={setCurrentSlideIndex}
            onChallengeSlide={(i) => navigate(`/challenge/${sessionId}?scope=slide&index=${i}`)}
          />
          <div style={{ marginTop: 16, marginBottom: 16 }}>
            <p>Current slide: {currentSlideIndex + 1} of {slideUrls.length}</p>
            {slideUrls[currentSlideIndex] && (
              <div
                style={{
                  maxWidth: '100%',
                  aspectRatio: '16 / 10',
                  background: '#111',
                  borderRadius: 8,
                  border: '1px solid #333',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  overflow: 'hidden',
                }}
              >
                <img
                  src={slideUrls[currentSlideIndex].startsWith('http') ? slideUrls[currentSlideIndex] : slideUrls[currentSlideIndex]}
                  alt={`Slide ${currentSlideIndex + 1}`}
                  style={{
                    maxWidth: '100%',
                    maxHeight: '100%',
                    width: 'auto',
                    height: 'auto',
                    objectFit: 'contain',
                  }}
                />
              </div>
            )}
          </div>

          {reconnecting && (
            <p style={{ color: '#fbbf24', marginBottom: 8 }}>Reconnecting…</p>
          )}
          {!isConnected && !reconnecting ? (
            <button onClick={handleStart} style={{ padding: '0.5rem 1rem' }}>
              Connect & start rehearsal
            </button>
          ) : isConnected ? (
            <div>
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
                End session
              </button>
            </div>
          ) : null}

          {error && !reconnecting && <p style={{ color: '#f87171', marginTop: 8 }}>{error}</p>}
          <LiveFeedback
            userTranscript={userTranscript}
            agentResponse={agentResponse}
            feedback={feedback}
            goAway={goAway}
          />
        </>
      )}
    </div>
  )
}
