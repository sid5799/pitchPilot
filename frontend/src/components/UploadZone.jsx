/** Drag-and-drop zone for PDF/PPTX (used by Upload page). */
export default function UploadZone({ onFileSelect, selectedFile }) {
  const handleDrop = (e) => {
    e.preventDefault()
    const f = e.dataTransfer?.files?.[0]
    if (f && (f.name.endsWith('.pdf') || f.name.endsWith('.pptx'))) onFileSelect(f)
  }
  return (
    <div
      onDrop={handleDrop}
      onDragOver={(e) => e.preventDefault()}
      style={{ border: '2px dashed #444', borderRadius: 8, padding: '2rem', textAlign: 'center' }}
    >
      {selectedFile ? <p>Selected: {selectedFile.name}</p> : <p>Drop PDF or PPTX here</p>}
    </div>
  )
}
