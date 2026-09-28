import Icon from './Icon.jsx'

const SEX_OPTIONS = [
  { value: '', label: 'Not specified' },
  { value: 'female', label: 'Female' },
  { value: 'male', label: 'Male' },
]

const DIET_OPTIONS = [
  { value: 'omnivore', label: 'Non-veg' },
  { value: 'eggetarian', label: 'Eggetarian' },
  { value: 'vegetarian', label: 'Vegetarian' },
  { value: 'vegan', label: 'Vegan' },
]

function Segmented({ options, value, onChange, disabled, label }) {
  return (
    <div className="segmented" role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          className={value === o.value ? 'on' : ''}
          disabled={disabled}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export default function PatientForm({ patient, setPatient, symptomCatalog, disabled }) {
  const update = (key, value) => setPatient((p) => ({ ...p, [key]: value }))
  const set = (key) => (e) =>
    update(key, e.target.type === 'checkbox' ? e.target.checked : e.target.value)

  function toggleSymptom(id) {
    setPatient((p) => ({
      ...p,
      symptoms: p.symptoms.includes(id) ? p.symptoms.filter((s) => s !== id) : [...p.symptoms, id],
    }))
  }

  const hasRedFlags = symptomCatalog.some((s) => s.red_flag)

  return (
    <section className="card">
      <div className="card-head">
        <div className="card-title">
          <div className="card-icon neutral">
            <Icon name="user" />
          </div>
          <div>
            <h2>
              Patient profile <span className="optional">Optional</span>
            </h2>
            <p>Personalises the diet plan and cross-checks reported symptoms</p>
          </div>
        </div>
      </div>

      <div className="card-body">
        <p className="section-label">Demographics</p>
        <fieldset className="form-grid" disabled={disabled}>
          <label className="field">
            <span>Age</span>
            <input
              className="input"
              type="number"
              min="1"
              max="120"
              value={patient.age}
              onChange={set('age')}
              placeholder="e.g. 28"
            />
          </label>
          <div className="field">
            <span className="field-label">Sex</span>
            <Segmented
              label="Sex"
              options={SEX_OPTIONS}
              value={patient.sex}
              disabled={disabled}
              onChange={(v) => update('sex', v)}
            />
          </div>
          {patient.sex === 'female' && (
            <label className="toggle span-2">
              <input type="checkbox" checked={patient.pregnant} onChange={set('pregnant')} />
              Currently pregnant
            </label>
          )}
        </fieldset>

        <p className="section-label">Diet &amp; lifestyle</p>
        <fieldset className="form-grid" disabled={disabled}>
          <div className="field span-2">
            <span className="field-label">Dietary preference</span>
            <Segmented
              label="Dietary preference"
              options={DIET_OPTIONS}
              value={patient.diet}
              disabled={disabled}
              onChange={(v) => update('diet', v)}
            />
          </div>
          <label className="field">
            <span>Region / cuisine</span>
            <input className="input" value={patient.region} onChange={set('region')} placeholder="e.g. South India" />
          </label>
          <label className="field">
            <span>Food allergies</span>
            <input
              className="input"
              value={patient.allergies}
              onChange={set('allergies')}
              placeholder="Comma-separated, e.g. peanuts, soy"
            />
          </label>
        </fieldset>

        {symptomCatalog.length > 0 && (
          <>
            <p className="section-label">Current symptoms</p>
            <fieldset className="chips" disabled={disabled}>
              {symptomCatalog.map((s) => {
                const on = patient.symptoms.includes(s.id)
                return (
                  <button
                    key={s.id}
                    type="button"
                    className={`chip ${on ? 'on' : ''}`}
                    aria-pressed={on}
                    onClick={() => toggleSymptom(s.id)}
                  >
                    {on ? <Icon name="check" size={14} strokeWidth={2.4} /> : s.red_flag && <span className="flag" />}
                    {s.label}
                  </button>
                )
              })}
            </fieldset>
            {hasRedFlags && (
              <div className="legend">
                <span className="flag" /> Red-flag symptom — needs prompt medical attention
              </div>
            )}
          </>
        )}
      </div>
    </section>
  )
}
