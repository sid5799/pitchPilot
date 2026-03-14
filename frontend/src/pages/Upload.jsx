import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadPresentation } from '../api/upload'

const SESSION_KEY = 'pitchpilot_session'

export default function Upload() {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  const handleDrop = (e) => {
    e.preventDefault()
    const f = e.dataTransfer?.files?.[0]
    if (f && (f.name.endsWith('.pdf') || f.name.endsWith('.pptx'))) setFile(f)
  }

  const handleSelect = (e) => {
    const f = e.target?.files?.[0]
    if (f) setFile(f)
  }

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const data = await uploadPresentation(file)
      const payload = { slide_urls: data.slide_urls, slide_count: data.slide_count }
      sessionStorage.setItem(`${SESSION_KEY}_${data.session_id}`, JSON.stringify(payload))
      navigate(`/rehearsal/${data.session_id}`, { state: payload })
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div style={{ padding: '2rem', maxWidth: 600, margin: '0 auto' }}>
      <h1>PitchPilot Live</h1>
      <p>Upload your presentation (PDF or PowerPoint) to start rehearsal.</p>
      <div
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
        style={{
          border: '2px dashed #444',
          borderRadius: 8,
          padding: '2rem',
          textAlign: 'center',
          margin: '1rem 0',
        }}
      >
        <input type="file" accept=".pdf,.pptx" onChange={handleSelect} />
        {file && <p>Selected: {file.name}</p>}
      </div>
      {error && <p style={{ color: '#f87171' }}>{error}</p>}
      <button
        onClick={handleUpload}
        disabled={!file || uploading}
        style={{ padding: '0.5rem 1rem', cursor: file && !uploading ? 'pointer' : 'not-allowed' }}
      >
        {uploading ? 'Uploading…' : 'Upload & Start Rehearsal'}
      </button>
    </div>
  )
}
