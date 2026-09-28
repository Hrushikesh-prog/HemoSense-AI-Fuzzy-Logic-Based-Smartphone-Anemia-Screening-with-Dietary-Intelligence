export default function SymptomsPanel({ symptoms, severity }) {
  const matchedIds = new Set(symptoms.matched.map((s) => s.id))
  const extraReported = symptoms.reported.filter((s) => !matchedIds.has(s.id))

  return (
    <section className="card">
      <div className="card-head">
        <h2>Symptoms</h2>
        <span className={`badge badge-concord-${symptoms.concordance}`}>
          {
            {
              concordant: 'Consistent with result',
              discordant: 'Not typical for result',
              not_reported: 'None reported',
            }[symptoms.concordance]
          }
        </span>
      </div>

      <p>{symptoms.note}</p>

      {symptoms.expected.length > 0 ? (
        <>
          <h3 className="subhead">Typical symptoms of {severity.toLowerCase()} anemia</h3>
          <ul className="symptom-list">
            {symptoms.expected.map((s) => (
              <li key={s.id} className={`${matchedIds.has(s.id) ? 'matched' : ''} ${s.red_flag ? 'red-flag' : ''}`}>
                <span className="mark" aria-hidden="true">{matchedIds.has(s.id) ? '✓' : '•'}</span>
                {s.label}
                {matchedIds.has(s.id) && <span className="muted small"> — you reported this</span>}
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="muted">No anemia-related symptoms are expected at a normal hemoglobin level.</p>
      )}

      {extraReported.length > 0 && (
        <>
          <h3 className="subhead">Other symptoms you reported</h3>
          <ul className="symptom-list">
            {extraReported.map((s) => (
              <li key={s.id} className={s.red_flag ? 'red-flag' : ''}>
                <span className="mark" aria-hidden="true">•</span>
                {s.label}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
