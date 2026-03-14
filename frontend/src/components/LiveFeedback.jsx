/**
 * Live session panel: user transcript, coach response grouped by slide, key takeaways (scrollable).
 */

// Extract slide number from start of string: "Slide 3: ..." or "For slide 2: ..." -> 3 or 2
function getSlideNumFromText(text) {
  if (!text || typeof text !== 'string') return null
  const trimmed = text.trim()
  const match = trimmed.match(/^(?:for\s+)?slide\s*(\d+)\s*[:\.]?\s*/i)
  return match ? parseInt(match[1], 10) : null
}

// Strip leading "Slide N:" or "For slide N:" so we don't repeat under the slide heading
function stripSlidePrefix(text) {
  if (!text || typeof text !== 'string') return text
  return text.replace(/^(?:for\s+)?slide\s*\d+\s*[:\.]?\s*/i, '').trim()
}

// Group feedback items by slide number; value = list of messages without "Slide N:" prefix
function groupFeedbackBySlide(feedback) {
  const bySlide = {}
  const noSlide = []
  for (const item of feedback) {
    const msg = typeof item === 'string' ? item : ''
    const num = getSlideNumFromText(msg)
    const stripped = stripSlidePrefix(msg)
    if (!stripped) continue
    if (num != null) {
      if (!bySlide[num]) bySlide[num] = []
      bySlide[num].push(stripped)
    } else {
      noSlide.push(stripped)
    }
  }
  return { bySlide, noSlide }
}

// Split coach response into segments by "Slide N:" so we can show under slide headers
function groupCoachResponseBySlide(agentResponse) {
  if (!agentResponse || !agentResponse.trim()) return {}
  const bySlide = {}
  // Match "Slide N:" or "Slide N " or "For slide N:" at start or after newline
  const parts = agentResponse.split(/(?=\b(?:for\s+)?slide\s*\d+\s*[:\.]?\s*)/i)
  for (const part of parts) {
    const trimmed = part.trim()
    if (!trimmed) continue
    const num = getSlideNumFromText(trimmed)
    const text = stripSlidePrefix(trimmed)
    if (!text) continue
    if (num != null) {
      bySlide[num] = (bySlide[num] || '') + (bySlide[num] ? '\n\n' : '') + text
    } else {
      bySlide[0] = (bySlide[0] || '') + (bySlide[0] ? '\n\n' : '') + trimmed
    }
  }
  if (Object.keys(bySlide).length === 0 && agentResponse.trim()) {
    bySlide[0] = agentResponse.trim()
  }
  return bySlide
}

export default function LiveFeedback({
  userTranscript = '',
  agentResponse = '',
  feedback = [],
  goAway = null,
  groupBySlide = true,
}) {
  const timeLeft = goAway?.time_left ?? null

  const { bySlide: feedbackBySlide, noSlide: feedbackNoSlide } = groupBySlide ? groupFeedbackBySlide(feedback) : { bySlide: {}, noSlide: feedback.map((f) => (typeof f === 'string' ? f : '')).filter(Boolean) }
  const coachBySlide = groupBySlide ? groupCoachResponseBySlide(agentResponse) : (agentResponse?.trim() ? { 0: agentResponse.trim() } : {})
  const hasUncategorized = true

  const allSlideNums = groupBySlide
    ? new Set([
        ...Object.keys(coachBySlide).map(Number).filter((n) => n > 0),
        ...Object.keys(feedbackBySlide).map(Number),
      ])
    : new Set()
  const sortedSlides = [...allSlideNums].sort((a, b) => a - b)
  const showGrouped = groupBySlide && (sortedSlides.length > 0 || feedbackNoSlide.length > 0 || coachBySlide[0] != null)

  return (
    <div
      style={{
        marginTop: 24,
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
      }}
    >
      {timeLeft && (
        <div
          style={{
            padding: '10px 14px',
            background: 'rgba(251, 191, 36, 0.12)',
            borderRadius: 8,
            fontSize: 13,
            color: '#fbbf24',
          }}
        >
          Session ending in {timeLeft}. You can reconnect to continue.
        </div>
      )}

      <div
        style={{
          background: '#18181b',
          borderRadius: 12,
          border: '1px solid #27272a',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid #27272a',
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: '0.05em',
            textTransform: 'uppercase',
            color: '#71717a',
          }}
        >
          Live transcript & feedback
        </div>

        <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Challenge: Agent first (speaks first); Rehearsal: What you said first */}
          {!groupBySlide && (
            <>
              {/* Agent – challenge mode, above "What you said" */}
              <section>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    letterSpacing: '0.04em',
                    color: '#a1a1aa',
                    marginBottom: 8,
                  }}
                >
                  Agent
                </div>
                <div
                  style={{
                    background: '#0f0f10',
                    borderRadius: 8,
                    borderLeft: '3px solid #22c55e',
                    overflow: 'hidden',
                  }}
                >
                  <div style={{ padding: '12px 14px' }}>
                    <div
                      style={{
                        fontSize: 14,
                        lineHeight: 1.55,
                        color: '#d4d4d8',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        minHeight: 44,
                      }}
                    >
                      {agentResponse || (
                        <span style={{ color: '#52525b' }}>Agent response will appear here.</span>
                      )}
                    </div>
                  </div>
                </div>
              </section>
              {/* What you said */}
              <section>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    letterSpacing: '0.04em',
                    color: '#a1a1aa',
                    marginBottom: 8,
                  }}
                >
                  What you said
                </div>
                <div
                  style={{
                    padding: '12px 14px',
                    background: '#0f0f10',
                    borderRadius: 8,
                    borderLeft: '3px solid #3b82f6',
                    fontSize: 14,
                    lineHeight: 1.5,
                    color: '#e4e4e7',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    minHeight: 44,
                  }}
                >
                  {userTranscript || (
                    <span style={{ color: '#52525b' }}>Your speech will appear here as you talk.</span>
                  )}
                </div>
              </section>
            </>
          )}

          {groupBySlide && (
            <>
              {/* Your transcript – rehearsal order */}
              <section>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    letterSpacing: '0.04em',
                    color: '#a1a1aa',
                    marginBottom: 8,
                  }}
                >
                  What you said
                </div>
                <div
                  style={{
                    padding: '12px 14px',
                    background: '#0f0f10',
                    borderRadius: 8,
                    borderLeft: '3px solid #3b82f6',
                    fontSize: 14,
                    lineHeight: 1.5,
                    color: '#e4e4e7',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    minHeight: 44,
                  }}
                >
                  {userTranscript || (
                    <span style={{ color: '#52525b' }}>Your speech will appear here as you talk.</span>
                  )}
                </div>
              </section>
            </>
          )}

          {/* Coach – grouped by slide (rehearsal only; challenge uses Agent block above) */}
          {groupBySlide && (
          <section>
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: '0.04em',
                color: '#a1a1aa',
                marginBottom: 8,
              }}
            >
              {groupBySlide ? 'Coach' : 'Agent'}
            </div>
            <div
              style={{
                background: '#0f0f10',
                borderRadius: 8,
                borderLeft: '3px solid #22c55e',
                overflow: 'hidden',
              }}
            >
              {!showGrouped ? (
                <div style={{ padding: '12px 14px' }}>
                  <div
                    style={{
                      fontSize: 14,
                      lineHeight: 1.55,
                      color: '#d4d4d8',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      minHeight: 44,
                    }}
                  >
                    {agentResponse || (
                      <span style={{ color: '#52525b' }}>Agent response will appear here.</span>
                    )}
                  </div>
                </div>
              ) : (
                <>
                  {sortedSlides.length === 0 && !hasUncategorized && (
                    <div style={{ padding: '12px 14px', fontSize: 14, color: '#52525b', minHeight: 44 }}>
                      Coach feedback will appear here as you speak.
                    </div>
                  )}
                  {sortedSlides.map((slideNum) => {
                    const coachText = coachBySlide[slideNum]
                    const bullets = feedbackBySlide[slideNum] || []
                    const hasContent = coachText || bullets.length > 0
                    if (!hasContent) return null
                    return (
                      <div
                        key={slideNum}
                        style={{
                          borderBottom: '1px solid #1f1f23',
                          padding: '12px 14px',
                        }}
                      >
                        <div
                          style={{
                            fontSize: 12,
                            fontWeight: 700,
                            color: '#22c55e',
                            marginBottom: 8,
                          }}
                        >
                          Slide {slideNum}
                        </div>
                        {coachText && (
                          <div
                            style={{
                              fontSize: 14,
                              lineHeight: 1.55,
                              color: '#d4d4d8',
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-word',
                              marginBottom: bullets.length ? 10 : 0,
                            }}
                          >
                            {coachText}
                          </div>
                        )}
                        {bullets.length > 0 && (
                          <ul
                            style={{
                              margin: 0,
                              paddingLeft: 18,
                              fontSize: 13,
                              lineHeight: 1.5,
                              color: '#a1a1aa',
                              listStyleType: 'disc',
                            }}
                          >
                            {bullets.map((msg, i) => (
                              <li key={i} style={{ marginBottom: 4 }}>
                                {msg}
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )
                  })}
                  {hasUncategorized && (
                    <div style={{ padding: '12px 14px', borderTop: '1px solid #1f1f23' }}>
                      {coachBySlide[0] && (
                        <div
                          style={{
                            fontSize: 14,
                            lineHeight: 1.55,
                            color: '#d4d4d8',
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                            marginBottom: feedbackNoSlide.length ? 10 : 0,
                          }}
                        >
                          {coachBySlide[0]}
                        </div>
                      )}
                      {feedbackNoSlide.length > 0 && (
                        <ul
                          style={{
                            margin: 0,
                            paddingLeft: 18,
                            fontSize: 13,
                            color: '#a1a1aa',
                            listStyleType: 'disc',
                          }}
                        >
                          {feedbackNoSlide.map((msg, i) => (
                            <li key={i} style={{ marginBottom: 4 }}>{msg}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          </section>
          )}

          {/* Key takeaways – rehearsal only; hidden in challenge */}
          {groupBySlide && (
          <section>
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: '0.04em',
                color: '#a1a1aa',
                marginBottom: 8,
              }}
            >
              Key takeaways
            </div>
            <div
              style={{
                maxHeight: 220,
                overflowY: 'auto',
                overflowX: 'hidden',
                padding: '12px 14px',
                background: '#0f0f10',
                borderRadius: 8,
                borderLeft: '3px solid #6366f1',
              }}
            >
              {feedback.length === 0 ? (
                <p style={{ margin: 0, fontSize: 13, color: '#52525b' }}>
                  Key takeaways will appear here (at least one per slide).
                </p>
              ) : (
                <ul
                  style={{
                    margin: 0,
                    paddingLeft: 20,
                    fontSize: 13,
                    lineHeight: 1.6,
                    color: '#a1a1aa',
                    listStyleType: 'disc',
                  }}
                >
                  {feedback.map((item, i) => (
                    <li key={i} style={{ marginBottom: 6 }}>
                      {typeof item === 'string' ? item : ''}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
          )}
        </div>
      </div>
    </div>
  )
}
