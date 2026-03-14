/** Q&A mode: predicted questions and evaluation (used in QnA page). */
export default function QnAPanel({ questions = [], currentAnswer, evaluation }) {
  return (
    <div>
      {questions.length > 0 && (
        <ul>
          {questions.map((q, i) => <li key={i}>{q}</li>)}
        </ul>
      )}
      {currentAnswer && <p>Your answer: {currentAnswer}</p>}
      {evaluation && <p><strong>Coach:</strong> {evaluation}</p>}
    </div>
  )
}
