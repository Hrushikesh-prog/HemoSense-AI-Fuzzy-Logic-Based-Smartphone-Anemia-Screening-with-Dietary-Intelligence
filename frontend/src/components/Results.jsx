import HbGauge from './HbGauge.jsx'
import Icon from './Icon.jsx'
import SymptomsPanel from './SymptomsPanel.jsx'
import DietPanel from './DietPanel.jsx'

const SEVERITY_CLASS = { Normal: 'normal', Mild: 'mild', Moderate: 'moderate', Severe: 'severe' }
const DIET_LABEL = { omnivore: 'Non-vegetarian', vegetarian: 'Vegetarian', eggetarian: 'Eggetarian', vegan: 'Vegan' }

function ProfileCard({ ctx, photoCount, analysed }) {
  const rows = [
    ['Age', ctx.age != null ? `${ctx.age} yrs` : '—'],
    ['Sex', ctx.sex || '—'],
    ['Diet', DIET_LABEL[ctx.diet] || ctx.diet || '—'],
    ['Region', ctx.region || '—'],
    ['Allergies', ctx.allergies?.length ? ctx.allergies.join(', ') : 'None'],
    ['Photos', `${analysed} of ${photoCount} analysed`],
  ]
  if (ctx.sex === 'female') rows.splice(2, 0, ['Pregnant', ctx.pregnant ? 'Yes' : 'No'])

  return (
    <section className="card">
      <div className="card-head">
        <div className="card-title">
          <div className="card-icon neutral">
            <Icon name="clipboard" />
          </div>
          <div>
            <h2>Screening details</h2>
            <p>Inputs used for this report</p>
          </div>
        </div>
      </div>
      <div className="card-body">
        <dl className="profile">
          {rows.map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  )
}

export default function Results({ result, photos, diet, onRetryDiet, onEdit, onStartOver }) {
  const { aggregate, per_image, symptoms, diet_plan, disclaimer } = result
  const verdict = aggregate.verdict
  const tone = verdict.status === 'inconclusive' ? 'inconclusive' : SEVERITY_CLASS[aggregate.severity_class]
  const analysed = per_image.filter((r) => !r.error).length
  const date = new Date().toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })

  return (
    <div className="results">
      <div className="toolbar no-print">
        <button className="btn btn-ghost" onClick={onEdit}>
          <Icon name="arrowLeft" size={16} /> Edit inputs
        </button>
        <div className="spacer" />
        <button className="btn" onClick={() => window.print()}>
          <Icon name="printer" size={16} /> Print report
        </button>
        <button className="btn btn-primary" onClick={onStartOver}>
          <Icon name="refresh" size={16} /> New screening
        </button>
      </div>

      <section className={`card verdict tone-${tone}`}>
        <div className="verdict-top">
          <div>
            <p className="eyebrow">
              <Icon name="activity" size={14} /> Screening report · {date}
            </p>
            <h1>{verdict.headline}</h1>
            <p className="verdict-summary">{verdict.summary}</p>
          </div>
          <div className="hb-readout">
            <div className="label">Estimated Hb</div>
            <div className="hb-value">{aggregate.predicted_hb_gdl.toFixed(1)}</div>
            <div className="hb-unit">g/dL</div>
            <span className={`badge badge-${SEVERITY_CLASS[aggregate.severity_class] || ''}`}>
              {aggregate.severity_class}
            </span>
          </div>
        </div>
        <div className="verdict-gauge">
          <HbGauge value={aggregate.predicted_hb_gdl} min={aggregate.min_hb_gdl} max={aggregate.max_hb_gdl} />
        </div>
        <dl className="stats">
          <div>
            <dt>Severity</dt>
            <dd>{aggregate.severity_class}</dd>
          </div>
          <div>
            <dt>Confidence</dt>
            <dd>{aggregate.confidence}</dd>
          </div>
          <div>
            <dt>Photo agreement</dt>
            <dd>{Math.round(aggregate.agreement * 100)}%</dd>
          </div>
          <div>
            <dt>Hb range</dt>
            <dd>
              {aggregate.min_hb_gdl.toFixed(1)}–{aggregate.max_hb_gdl.toFixed(1)} <small>g/dL</small>
            </dd>
          </div>
        </dl>
      </section>

      {symptoms.urgent && (
        <div className="alert alert-error" role="alert">
          <Icon name="alert" size={20} />
          <div>
            <div className="alert-title">Seek medical care promptly</div>
            <p>
              {symptoms.red_flags.length > 0
                ? `You reported ${symptoms.red_flags.map((s) => s.label.toLowerCase()).join(', ')} — these need urgent attention regardless of the screening result.`
                : 'The estimate falls in the severe range. Please see a doctor within 24–48 hours.'}
            </p>
          </div>
        </div>
      )}

      <div className="two-col">
        <SymptomsPanel symptoms={symptoms} severity={aggregate.severity_class} />
        <ProfileCard ctx={result.userContext} photoCount={per_image.length} analysed={analysed} />
      </div>

      <DietPanel plan={diet_plan} diet={diet} onRetry={onRetryDiet} />

      <section className="card">
        <div className="card-head">
          <div className="card-title">
            <div className="card-icon neutral">
              <Icon name="image" />
            </div>
            <div>
              <h2>Per-photo analysis</h2>
              <p>
                Original vs. fuzzy colour-corrected conjunctiva region · spread ±{aggregate.std_hb_gdl.toFixed(2)} g/dL
              </p>
            </div>
          </div>
        </div>
        <div className="card-body">
          <ul className="photo-results">
            {per_image.map((r) => (
              <li key={r.index} className={r.error ? 'failed' : ''}>
                <div className="photo-pair">
                  <figure>
                    <img src={photos[r.index]?.url} alt={`Photo ${r.index + 1}`} />
                    <figcaption>#{r.index + 1}</figcaption>
                  </figure>
                  {r.roi_thumbnail && (
                    <figure>
                      <img src={r.roi_thumbnail} alt={`Conjunctiva region ${r.index + 1}`} />
                      <figcaption>ROI</figcaption>
                    </figure>
                  )}
                </div>
                {r.error ? (
                  <p className="error-text">Skipped: {r.error}</p>
                ) : (
                  <div className="photo-meta">
                    <strong>{r.predicted_hb_gdl.toFixed(1)} g/dL</strong>
                    <span className={`badge badge-${SEVERITY_CLASS[r.severity_class]}`}>{r.severity_class}</span>
                    {r.erythema_index?.corrected != null && (
                      <span className="ei">EI {r.erythema_index.corrected.toFixed(3)}</span>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <div className="disclaimer">
        <Icon name="info" size={16} />
        <span>
          {disclaimer} Model: {result.model}.
        </span>
      </div>
    </div>
  )
}
