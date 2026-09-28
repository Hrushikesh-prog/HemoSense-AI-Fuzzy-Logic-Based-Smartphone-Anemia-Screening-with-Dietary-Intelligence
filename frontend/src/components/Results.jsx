import HbGauge from './HbGauge.jsx'
import SymptomsPanel from './SymptomsPanel.jsx'
import DietPanel from './DietPanel.jsx'

const SEVERITY_CLASS = { Normal: 'normal', Mild: 'mild', Moderate: 'moderate', Severe: 'severe' }

export default function Results({ result, photos, diet, onRetryDiet, onEdit, onStartOver }) {
  const { aggregate, per_image, symptoms, diet_plan, disclaimer } = result
  const verdict = aggregate.verdict
  const tone = verdict.status === 'inconclusive' ? 'inconclusive' : SEVERITY_CLASS[aggregate.severity_class]

  return (
    <div className="results">
      <div className="results-toolbar no-print">
        <button className="btn" onClick={onEdit}>← Edit inputs</button>
        <div className="spacer" />
        <button className="btn" onClick={() => window.print()}>Print / save report</button>
        <button className="btn btn-primary" onClick={onStartOver}>New screening</button>
      </div>

      <section className={`card verdict verdict-${tone}`}>
        <div className="verdict-main">
          <p className="eyebrow">Screening result</p>
          <h1>{verdict.headline}</h1>
          <p>{verdict.summary}</p>
          <dl className="stats">
            <div>
              <dt>Estimated Hb</dt>
              <dd>
                {aggregate.predicted_hb_gdl.toFixed(1)} <small>g/dL</small>
              </dd>
            </div>
            <div>
              <dt>Severity</dt>
              <dd>{aggregate.severity_class}</dd>
            </div>
            <div>
              <dt>Confidence</dt>
              <dd>{aggregate.confidence}</dd>
            </div>
            <div>
              <dt>Photos agreeing</dt>
              <dd>{Math.round(aggregate.agreement * 100)}%</dd>
            </div>
          </dl>
        </div>
        <HbGauge value={aggregate.predicted_hb_gdl} min={aggregate.min_hb_gdl} max={aggregate.max_hb_gdl} />
      </section>

      {symptoms.urgent && (
        <div className="alert alert-error" role="alert">
          <strong>Seek medical care promptly.</strong>{' '}
          {symptoms.red_flags.length > 0
            ? `You reported ${symptoms.red_flags.map((s) => s.label.toLowerCase()).join(', ')} — these need urgent attention regardless of the screening result.`
            : 'The estimate falls in the severe range. Please see a doctor within 24–48 hours.'}
        </div>
      )}

      <SymptomsPanel symptoms={symptoms} severity={aggregate.severity_class} />

      <DietPanel plan={diet_plan} diet={diet} onRetry={onRetryDiet} />

      <section className="card">
        <div className="card-head">
          <h2>Per-photo analysis</h2>
          <span className="muted small">
            Hb range {aggregate.min_hb_gdl.toFixed(1)}–{aggregate.max_hb_gdl.toFixed(1)} g/dL · spread ±
            {aggregate.std_hb_gdl.toFixed(2)}
          </span>
        </div>
        <ul className="photo-results">
          {per_image.map((r) => (
            <li key={r.index} className={r.error ? 'failed' : ''}>
              <div className="photo-pair">
                <figure>
                  <img src={photos[r.index]?.url} alt={`Photo ${r.index + 1}`} />
                  <figcaption>Original</figcaption>
                </figure>
                {r.roi_thumbnail && (
                  <figure>
                    <img src={r.roi_thumbnail} alt={`Conjunctiva region ${r.index + 1}`} />
                    <figcaption>Fuzzy-corrected ROI</figcaption>
                  </figure>
                )}
              </div>
              {r.error ? (
                <p className="small error-text">Skipped: {r.error}</p>
              ) : (
                <div className="photo-meta">
                  <strong>{r.predicted_hb_gdl.toFixed(1)} g/dL</strong>
                  <span className={`badge badge-${SEVERITY_CLASS[r.severity_class]}`}>{r.severity_class}</span>
                  {r.erythema_index?.corrected != null && (
                    <span className="muted small">EI {r.erythema_index.corrected.toFixed(3)}</span>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      </section>

      <p className="disclaimer">
        {disclaimer} Model: {result.model}.
      </p>
    </div>
  )
}
