import { useCallback, useRef, useState } from 'react'


const WS_PATH = '/ws'
const USER_ID = 'default'

/**
 * Get WebSocket URL for Live session (uses Vite proxy in dev).
 * options: { mode: 'challenge', scope: 'all'|'slide', slideIndex: number } for Challenge Me.
 */
function getWsUrl(sessionId, options = null) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  let url = `${protocol}//${host}${WS_PATH}/${USER_ID}/${sessionId}`
  if (options?.mode === 'challenge') {
    const params = new URLSearchParams({ mode: 'challenge', scope: options.scope || 'all' })
    if (options.scope === 'slide' && typeof options.slideIndex === 'number') {
      params.set('slide_index', String(options.slideIndex))
    }
    url += `?${params.toString()}`
  }
  return url
}

/**
 * Capture mic and send 16-bit PCM 16kHz chunks over WebSocket.
 */
function useMicPump(wsRef, onError) {
  const streamRef = useRef(null)
  const contextRef = useRef(null)
  const processorRef = useRef(null)

  const stopMic = useCallback(() => {
    if (processorRef.current && contextRef.current) {
      try {
        processorRef.current.disconnect()
        contextRef.current.close()
      } catch (_) {}
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    processorRef.current = null
    contextRef.current = null
  }, [])

  const startMic = useCallback(async () => {
    if (streamRef.current) return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      // Ensure playback context exists and is resumed on user gesture so agent audio can play later
      const Ctx = window.AudioContext || window.webkitAudioContext
      if (Ctx) {
        if (!playbackCtx) playbackCtx = new Ctx({ sampleRate: PLAYBACK_SAMPLE_RATE })
        if (playbackCtx.state === 'suspended') playbackCtx.resume()
      }
      const sampleRate = 16000
      const ctx = new Ctx({ sampleRate })
      contextRef.current = ctx
      const source = ctx.createMediaStreamSource(stream)
      // 20–40ms chunks minimize latency (best practice); 512 samples @ 16kHz = 32ms
      const bufferSize = 512
      const processor = ctx.createScriptProcessor(bufferSize, 1, 1)
      processor.onaudioprocess = (e) => {
        const ws = wsRef.current
        if (!ws || ws.readyState !== WebSocket.OPEN) return
        const input = e.inputBuffer.getChannelData(0)
        const pcm = floatTo16BitPCM(input)
        ws.send(pcm)
      }
      source.connect(processor)
      processor.connect(ctx.destination)
      processorRef.current = processor
    } catch (err) {
      onError?.(err.message)
    }
  }, [onError])

  return { startMic, stopMic }
}

function floatTo16BitPCM(float32Array) {
  const buffer = new ArrayBuffer(float32Array.length * 2)
  const view = new DataView(buffer)
  for (let i = 0; i < float32Array.length; i++) {
    const s = Math.max(-1, Math.min(1, float32Array[i]))
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true)
  }
  return buffer
}

const PLAYBACK_SAMPLE_RATE = 24000
let playbackCtx = null
const agentAudioQueue = []
let agentAudioPlaying = false

/** Decode base64 or base64url to binary string for atob. */
function decodeBase64(base64Str) {
  if (typeof base64Str !== 'string') return ''
  const normalized = base64Str.replace(/-/g, '+').replace(/_/g, '/')
  const pad = normalized.length % 4
  const padded = pad ? normalized + '='.repeat(4 - pad) : normalized
  return atob(padded)
}

/**
 * Decode 16-bit little-endian PCM to float32 and play (or queue).
 * API output: 24 kHz, 16-bit PCM, little-endian.
 */
function playAgentAudio(base64Pcm) {
  try {
    const binary = decodeBase64(base64Pcm)
    const byteLength = binary.length
    const numSamples = (byteLength >> 1)
    if (numSamples === 0) return
    const bytes = new Uint8Array(numSamples * 2)
    for (let i = 0; i < bytes.length; i++) bytes[i] = binary.charCodeAt(i)
    const view = new DataView(bytes.buffer)
    const float32 = new Float32Array(numSamples)
    for (let i = 0; i < numSamples; i++) {
      const s = view.getInt16(i * 2, true)
      float32[i] = s / (s < 0 ? 0x8000 : 0x7fff)
    }
    const Ctx = window.AudioContext || window.webkitAudioContext
    if (!Ctx) return
    if (!playbackCtx) playbackCtx = new Ctx({ sampleRate: PLAYBACK_SAMPLE_RATE })
    if (playbackCtx.state === 'suspended') playbackCtx.resume()
    const buf = playbackCtx.createBuffer(1, float32.length, PLAYBACK_SAMPLE_RATE)
    buf.getChannelData(0).set(float32)
    const play = () => {
      const src = playbackCtx.createBufferSource()
      src.buffer = buf
      src.connect(playbackCtx.destination)
      src.onended = () => {
        agentAudioPlaying = false
        if (agentAudioQueue.length > 0) {
          const next = agentAudioQueue.shift()
          agentAudioPlaying = true
          next()
        }
      }
      src.start()
    }
    if (agentAudioPlaying) {
      agentAudioQueue.push(play)
    } else {
      agentAudioPlaying = true
      play()
    }
  } catch (_) {}
}

/**
 * WebSocket hook for Live session: send audio/slide, receive audio/transcript.
 */
const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_BACKOFF_MS = 1500

export function useLiveSession(sessionId, slideUrls = [], options = null) {
  const [isConnected, setIsConnected] = useState(false)
  const [reconnecting, setReconnecting] = useState(false)
  const [latestUserText, setLatestUserText] = useState('')
  const [latestAgentText, setLatestAgentText] = useState('')
  const [feedback, setFeedback] = useState([])
  const [error, setError] = useState(null)
  const [goAway, setGoAway] = useState(null)
  const wsRef = useRef(null)
  const wsOptionsRef = useRef(null)
  const intentionalCloseRef = useRef(false)
  const reconnectAttemptsRef = useRef(0)
  const reconnectTimeoutRef = useRef(null)

  const { startMic, stopMic } = useMicPump(wsRef, setError)

  const attachHandlers = useCallback((ws) => {
    ws.binaryType = 'arraybuffer'
    ws.onopen = () => {
      setIsConnected(true)
      setReconnecting(false)
      setError(null)
      reconnectAttemptsRef.current = 0
    }
    ws.onclose = () => {
      setIsConnected(false)
      wsRef.current = null
      if (intentionalCloseRef.current) {
        intentionalCloseRef.current = false
        return
      }
      setReconnecting(true)
      reconnectAttemptsRef.current += 1
      if (reconnectAttemptsRef.current > MAX_RECONNECT_ATTEMPTS) {
        setError('Connection lost. Click "Connect & start rehearsal" to try again.')
        setReconnecting(false)
        return
      }
      const delay = RECONNECT_BACKOFF_MS * reconnectAttemptsRef.current
      reconnectTimeoutRef.current = setTimeout(() => {
        reconnectTimeoutRef.current = null
        if (!sessionId) return
        setError(null)
        const url = getWsUrl(sessionId, wsOptionsRef.current)
        const next = new WebSocket(url)
        wsRef.current = next
        attachHandlers(next)
      }, delay)
    }
    ws.onerror = () => setError('WebSocket error')
    ws.onmessage = (event) => {
      if (typeof event.data !== 'string') return
      try {
        const data = JSON.parse(event.data)
        if (data.error) {
          setError(data.error)
          return
        }
        if (data.reconnecting) {
          setError(null)
          setGoAway(null)
          setReconnecting(true)
          return
        }
        if (data.go_away) {
          setGoAway(data.go_away)
        }
        const rawOut = (data.outputTranscription?.text ?? data.output_transcription?.text)?.trim()
        if (rawOut != null && rawOut !== '') {
          // Remove tool syntax, XML, and internal cues not meant for display
          let outText = rawOut
            .replace(/<\/?record_feedback[^>]*>/gi, '')
            .replace(/<record_feedback[^>]*>/gi, '')
            .replace(/record_feedback\s*\(\s*feedback_type\s*=\s*["']?\w+["']?\s*,\s*message\s*=\s*(?:"[^"]*"|[^)]*)\)/gi, '')
            .replace(/<ctrl\d+>/gi, '')
            .replace(/<[a-zA-Z][^>]*>/g, '')
            .replace(/\[Presenter is now on slide \d+\]/gi, '')
            .replace(/\s{2,}/g, ' ')
            .trim()
          // Trim stray punctuation left after removing tool calls (e.g. ".)" or ").")
          outText = outText.replace(/^\s*[.)]\s*|\s*[.(]\s*$/g, '').trim()
          if (outText) {
            setLatestAgentText((prev) => {
              if (prev && (outText === prev || outText.startsWith(prev))) return outText
              return prev ? prev + ' ' + outText : outText
            })
          }
        }
        const inText = (data.inputTranscription?.text ?? data.input_transcription?.text)?.trim()
        if (inText != null && inText !== '') {
          setLatestUserText((prev) => {
            // Cumulative: API sent full phrase so far (e.g. "hello" then "hello how")
            if (prev && (inText === prev || inText.startsWith(prev))) return inText
            // Incremental: append new word/phrase so previous words aren't replaced
            return prev ? prev + ' ' + inText : inText
          })
        }
        const parts = data.content?.parts
        if (Array.isArray(parts)) {
          const skipPlayback = !!data.interrupted
          if (skipPlayback) {
            agentAudioQueue.length = 0
          }
          for (const part of parts) {
            const fc = part.function_call ?? part.functionCall
            if (fc?.name === 'record_feedback') {
              const args = fc.args ?? fc.arguments ?? {}
              if (args.message) setFeedback((f) => [...f.slice(-19), args.message])
            }
            const inline = part.inline_data ?? part.inlineData
            if (inline?.data && !skipPlayback && wsOptionsRef.current?.mode === 'challenge') {
              playAgentAudio(inline.data)
            }
          }
        }
        const toolCalls = data.toolCall?.functionCalls ?? data.tool_call?.function_calls
        if (Array.isArray(toolCalls)) {
          for (const call of toolCalls) {
            if (call.name === 'record_feedback' && call.args?.message) {
              setFeedback((f) => [...f.slice(-19), call.args.message])
            }
          }
        }
      } catch (_) {}
    }
  }, [sessionId])

  const connect = useCallback(() => {
    if (!sessionId) return
    // Prepare playback context on user gesture (Connect/Start challenge) so agent speech can play
    const Ctx = window.AudioContext || window.webkitAudioContext
    if (Ctx) {
      if (!playbackCtx) playbackCtx = new Ctx({ sampleRate: PLAYBACK_SAMPLE_RATE })
      if (playbackCtx.state === 'suspended') playbackCtx.resume()
    }
    wsOptionsRef.current = options
    intentionalCloseRef.current = false
    setError(null)
    setGoAway(null)
    setReconnecting(false)
    reconnectAttemptsRef.current = 0
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    const url = getWsUrl(sessionId, options)
    const ws = new WebSocket(url)
    wsRef.current = ws
    attachHandlers(ws)
  }, [sessionId, options, attachHandlers])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    intentionalCloseRef.current = true
    stopMic()
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setIsConnected(false)
    setReconnecting(false)
    setLatestUserText('')
    setLatestAgentText('')
  }, [stopMic])

  const sendAudio = useCallback((chunk) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(chunk)
  }, [])

  const sendText = useCallback((text) => {
    const ws = wsRef.current
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'text', text }))
  }, [])

  const lastSlideSendRef = useRef(0)
  const SLIDE_SEND_INTERVAL_MS = 1100

  const sendSlideIndex = useCallback(
    async (index) => {
      const ws = wsRef.current
      if (!ws || ws.readyState !== WebSocket.OPEN || !slideUrls?.[index]) return
      const now = Date.now()
      if (now - lastSlideSendRef.current < SLIDE_SEND_INTERVAL_MS) return
      lastSlideSendRef.current = now
      try {
        const url = slideUrls[index]
        const fullUrl = url.startsWith('http') ? url : `${window.location.origin}${url}`
        const res = await fetch(fullUrl)
        const blob = await res.blob()
        const reader = new FileReader()
        reader.onload = () => {
          const base64 = reader.result.split(',')[1]
          ws.send(JSON.stringify({ type: 'image', data: base64, mimeType: 'image/jpeg', slideIndex: index + 1 }))
        }
        reader.readAsDataURL(blob)
      } catch (e) {
        console.warn('Failed to send slide image', e)
      }
    },
    [slideUrls]
  )

  return {
    connect,
    disconnect,
    sendAudio,
    sendSlideIndex,
    sendText,
    startMic,
    stopMic,
    isConnected,
    reconnecting,
    userTranscript: latestUserText,
    agentResponse: latestAgentText,
    feedback,
    error,
    goAway,
  }
}
