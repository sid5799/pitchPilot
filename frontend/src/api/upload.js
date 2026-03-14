/**
 * Upload presentation and get session_id + slide URLs.
 * @param {File} file - PDF or PPTX
 * @returns {Promise<{ session_id: string, slide_urls: string[] }>}
 */
export async function uploadPresentation(file) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch('/api/upload', { method: 'POST', body: formData })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Upload failed: ${res.status}`)
  }
  return res.json()
}
