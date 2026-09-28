export default function PatientForm({ patient, setPatient, symptomCatalog, disabled }) {
  const set = (key) => (e) =>
    setPatient((p) => ({
      ...p,
      [key]: e.target.type === 'checkbox' ? e.target.checked : e.target.value,
    }))

  function toggleSymptom(id) {
    setPatient((p) => ({
      ...p,
      symptoms: p.symptoms.includes(id) ? p.symptoms.filter((s) => s !== id) : [...p.symptoms, id],
    }))
  }

  return (
    <section className="card">
      <div className="card-head">
        <h2>
          <span className="step">2</span> Patient details <span className="muted small">(optional)</span>
        </h2>
      </div>
      <p className="muted small">Used to personalise the diet plan and cross-check symptoms.</p>

      <fieldset className="grid" disabled={disabled}>
        <label>
          Age
          <input type="number" min="1" max="120" value={patient.age} onChange={set('age')} placeholder="e.g. 28" />
        </label>
        <label>
          Sex
          <select value={patient.sex} onChange={set('sex')}>
            <option value="">Prefer not to say</option>
            <option value="female">Female</option>
            <option value="male">Male</option>
          </select>
        </label>
        <label>
          Diet
          <select value={patient.diet} onChange={set('diet')}>
            <option value="omnivore">Non-vegetarian</option>
            <option value="vegetarian">Vegetarian</option>
            <option value="eggetarian">Eggetarian</option>
            <option value="vegan">Vegan</option>
          </select>
        </label>
        <label>
          Region / cuisine
          <input value={patient.region} onChange={set('region')} placeholder="e.g. South India" />
        </label>
        <label className="span-2">
          Food allergies
          <input value={patient.allergies} onChange={set('allergies')} placeholder="Comma-separated, e.g. peanuts, soy" />
        </label>
        {patient.sex === 'female' && (
          <label className="checkbox span-2">
            <input type="checkbox" checked={patient.pregnant} onChange={set('pregnant')} />
            Currently pregnant
          </label>
        )}
      </fieldset>

      {symptomCatalog.length > 0 && (
        <>
          <h3 className="subhead">Symptoms you are experiencing</h3>
          <fieldset className="chips" disabled={disabled}>
            {symptomCatalog.map((s) => {
              const on = patient.symptoms.includes(s.id)
              return (
                <button
                  key={s.id}
                  type="button"
                  className={`chip ${on ? 'on' : ''} ${s.red_flag ? 'red-flag' : ''}`}
                  aria-pressed={on}
                  onClick={() => toggleSymptom(s.id)}
                >
                  {on ? '✓ ' : ''}
                  {s.label}
                </button>
              )
            })}
          </fieldset>
        </>
      )}
    </section>
  )
}
