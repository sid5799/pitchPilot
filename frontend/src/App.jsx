import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Upload from './pages/Upload'
import Rehearsal from './pages/Rehearsal'
import QnA from './pages/QnA'
import Challenge from './pages/Challenge'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Upload />} />
        <Route path="/rehearsal/:sessionId" element={<Rehearsal />} />
        <Route path="/qna/:sessionId" element={<QnA />} />
        <Route path="/challenge/:sessionId" element={<Challenge />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
