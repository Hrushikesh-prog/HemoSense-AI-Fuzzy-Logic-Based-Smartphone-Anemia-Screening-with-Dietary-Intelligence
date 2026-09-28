import Icon from './Icon.jsx'

const CONCORDANCE = {
  concordant: 'Consistent with result',
  discordant: 'Not typical for result',
  not_reported: 'None reported',
}

function SymptomList({ items, matchedIds }) {
  return (
    <ul className="symptom-list">
      {items.map((s) => {
        const matched = matchedIds.has(s.id)
        return (
          <li key={s.id} className={`${matched ? 'matched' : ''} ${s.red_flag ? 'red-flag' : ''}`}>
            <span className="mark" aria-hidden="true">
              <Icon name="check" size={11} strokeWidth={3} />
            </span>
            {s.label}
            {matched && <span className="sr-only"> (you reported this)</span>}
          </li>
        )
      })}
    </ul>
  )
}

export default function SymptomsPanel({ symptoms, severity }) {
  const matchedIds = new Set(symptoms.matched.map((s) => s.id))
  const extraReported = symptoms.reported.filter((s) => !matchedIds.has(s.id))

  return (
    <section className="card">
      <div className="card-head">
        <div className="card-title">
          <div className="card-icon">
            <Icon name="activity" />
          </div>
          <div>
            <h2>Symptom correlation</h2>
            <p>Reported symptoms vs. those typical for this result</p>
          </div>
        </div>
        <span className={`badge badge-concord-${symptoms.concordance}`}>{CONCORDANCE[symptoms.concordance]}</span>
      </div>

      <div className="card-body">
        <p className="note">{symptoms.note}</p>

        {symptoms.expected.length > 0 ? (
          <>
            <p className="section-label">Typical of {severity.toLowerCase()} anemia</p>
            <SymptomList items={symptoms.expected} matchedIds={matchedIds} />
          </>
        ) : (
          <p className="muted small">No anemia-related symptoms are expected at a normal hemoglobin level.</p>
        )}

        {extraReported.length > 0 && (
          <>
            <p className="section-label">Other symptoms reported</p>
            <SymptomList items={extraReported} matchedIds={new Set(extraReported.map((s) => s.id))} />
          </>
        )}
      </div>
    </section>
  )
}
