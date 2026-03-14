import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useLiveSession } from '../hooks/useLiveSession'
import LiveFeedback from '../components/LiveFeedback'
import QnAPanel from '../components/QnAPanel'

const SESSION_KEY = 'pitchpilot_session'

const QNA_PROMPT = (questions) =>
  `We're now in Q&A mode. You are the audience. Ask the user these questions one at a time and briefly evaluate each answer before moving to the next. Questions: ${JSON.stringify(questions)}. Start by asking the first question.`

export default function QnA() {
  const { sessionId } = useParams()
  const [questions, setQuestions] = useState([])
  const [loadingQuestions, setLoadingQuestions] = useState(false)
  const [questionsError, setQuestionsError] = useState(null)
  const qnaStartedRef = useRef(false)

  const {
    connect,
    disconnect,
    sendText,
    startMic,
    stopMic,
    isConnected,
    reconnecting,
    userTranscript,
    agentResponse,
    feedback,
    error,
    goAway,
  } = useLiveSession(sessionId, [])

  useEffect(() => {
    return () => disconnect()
  }, [disconnect])

  const fetchQuestions = async () => {
    setLoadingQuestions(true)
    setQuestionsError(null)
    try {
      const res = await fetch(`/api/session/${sessionId}/generate-questions?max_questions=5`, { method: 'POST' })
      if (!res.ok) throw new Error((await res.json()).detail || 'Failed to generate questions')
      const data = await res.json()
      const qs = data.questions || []
      setQuestions(qs)
      return qs
    } catch (e) {
      setQuestionsError(e.message)
      return []
    } finally {
      setLoadingQuestions(false)
    }
  }

  useEffect(() => {
    if (isConnected && questions.length > 0 && !qnaStartedRef.current) {
      qnaStartedRef.current = true
      sendText(QNA_PROMPT(questions))
    }
  }, [isConnected, questions, sendText])

  const handleStartQnA = () => {
    if (questions.length > 0) {
      connect()
    } else {
      fetchQuestions().then((qs) => {
        if (qs.length) connect()
      })
    }
  }

  const handleStartWithNewQuestions = () => {
    qnaStartedRef.current = false
    fetchQuestions().then((qs) => {
      if (qs.length) connect()
    })
  }

  const [micActive, setMicActive] = useState(false)
  const handleMicToggle = () => {
    if (micActive) {
      stopMic()
      setMicActive(false)
    } else {
      startMic()
      setMicActive(true)
    }
  }

  return (
    <div style={{ padding: '2rem', maxWidth: 700, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h1>Live Q&A</h1>
        <Link to="/">Upload</Link>
        <Link to={`/rehearsal/${sessionId}`}>Rehearsal</Link>
      </div>

      {!questions.length && !loadingQuestions && (
        <div style={{ marginBottom: 16 }}>
          <p>Generate predicted audience questions from your slides, then practice answering them with the coach.</p>
          <button onClick={fetchQuestions} disabled={loadingQuestions} style={{ padding: '0.5rem 1rem' }}>
            {loadingQuestions ? 'Generating…' : 'Generate questions'}
          </button>
          {questionsError && <p style={{ color: '#f87171', marginTop: 8 }}>{questionsError}</p>}
        </div>
      )}

      {questions.length > 0 && (
        <>
          <QnAPanel questions={questions} />
          {reconnecting && (
            <p style={{ color: '#fbbf24', marginTop: 16 }}>Reconnecting…</p>
          )}
          {!isConnected && !reconnecting ? (
            <div style={{ marginTop: 16 }}>
              <button onClick={handleStartQnA} style={{ padding: '0.5rem 1rem', marginRight: 8 }}>
                Start Q&A practice
              </button>
              <button onClick={handleStartWithNewQuestions} style={{ padding: '0.5rem 1rem' }}>
                Regenerate questions & start
              </button>
            </div>
          ) : isConnected ? (
            <div style={{ marginTop: 16 }}>
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
              <button onClick={disconnect} style={{ padding: '0.5rem 1rem' }}>
                End Q&A
              </button>
            </div>
          ) : null}
        </>
      )}

      {error && !reconnecting && <p style={{ color: '#f87171', marginTop: 8 }}>{error}</p>}
      <LiveFeedback
        userTranscript={userTranscript}
        agentResponse={agentResponse}
        feedback={feedback}
        goAway={goAway}
      />
    </div>
  )
}
