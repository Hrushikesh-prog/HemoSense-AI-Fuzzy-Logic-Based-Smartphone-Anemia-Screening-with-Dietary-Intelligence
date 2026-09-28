import { useEffect, useState } from 'react'
import {
  MAX_IMAGES,
  MIN_IMAGES,
  getDietRecommendations,
  getHealth,
  getSymptoms,
  screenBatch,
} from './api.js'
import Header from './components/Header.jsx'
import Icon from './components/Icon.jsx'
import PhotoUploader from './components/PhotoUploader.jsx'
import PatientForm from './components/PatientForm.jsx'
import Results from './components/Results.jsx'

const EMPTY_PATIENT = {
  age: '',
  sex: '',
  pregnant: false,
  diet: 'omnivore',
  region: '',
  allergies: '',
  symptoms: [],
}

// Display-only stages shown while /screen/batch runs (mirrors api/pipeline.py).
const STAGES = ['Locating conjunctiva', 'Fuzzy colour correction', 'CNN hemoglobin estimate', 'Aggregating results']

function toUserContext(p) {
  const ctx = { diet: p.diet, symptoms: p.symptoms }
  if (p.age !== '') ctx.age = Number(p.age)
  if (p.sex) ctx.sex = p.sex
  if (p.sex === 'female') ctx.pregnant = p.pregnant
  if (p.region.trim()) ctx.region = p.region.trim()
  const allergies = p.allergies.split(',').map((a) => a.trim()).filter(Boolean)
  if (allergies.length) ctx.allergies = allergies
  return ctx
}

function Hero({ health }) {
  const t = health?.metrics?.test_metrics
  const bin = t?.binary_screening
  return (
    <section className="hero">
      <div>
        <p className="eyebrow">
          <Icon name="droplet" size={14} /> Fuzzy logic · CNN · Dietary AI
        </p>
        <h1>Estimate hemoglobin from a photo of the eye</h1>
        <p className="hero-lead">
          Each conjunctiva photo is colour-corrected with fuzzy logic, analysed by a convolutional neural
          network, and combined into a single hemoglobin estimate with symptom correlation and a personalised
          recovery diet.
        </p>
      </div>
      {t && (
        <div className="metrics">
          <div className="metric">
            <div className="metric-value">
              ±{t.overall_mae.toFixed(2)}
              <small>g/dL</small>
            </div>
            <div className="metric-label">Mean abs. error</div>
          </div>
          {bin && (
            <>
              <div className="metric">
                <div className="metric-value">{Math.round(bin.sensitivity * 100)}%</div>
                <div className="metric-label">Sensitivity</div>
              </div>
              <div className="metric">
                <div className="metric-value">{Math.round(bin.specificity * 100)}%</div>
                <div className="metric-label">Specificity</div>
              </div>
            </>
          )}
          <p className="metrics-note">
            Held-out test set, n = {t.n_test}
            {bin && ` · anemia threshold ${bin.threshold_g_dl} g/dL`}
          </p>
        </div>
      )}
    </section>
  )
}

function Stepper({ step }) {
  const steps = ['Capture photos', 'Patient profile', 'Review report']
  return (
    <ol className="stepper no-print">
      {steps.map((s, i) => (
        <li key={s} className={i < step ? 'done' : i === step ? 'active' : ''}>
          <span className="num-dot">{i < step ? <Icon name="check" size={12} strokeWidth={3} /> : i + 1}</span>
          {s}
        </li>
      ))}
    </ol>
  )
}

function AnalyzingSteps() {
  const [stage, setStage] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setStage((s) => Math.min(s + 1, STAGES.length - 1)), 1400)
    return () => clearInterval(t)
  }, [])
  return (
    <ul className="progress-steps" aria-live="polite">
      {STAGES.map((s, i) => (
        <li key={s} className={i < stage ? 'done' : i === stage ? 'active' : ''}>
          <span className="ps-icon">
            {i < stage ? (
              <Icon name="check" size={12} strokeWidth={3} />
            ) : i === stage ? (
              <span className="spinner dark" style={{ width: 18, height: 18 }} />
            ) : null}
          </span>
          {s}
        </li>
      ))}
    </ul>
  )
}

function SummaryPanel({ photos, patient, health, healthError, analyzing, canAnalyze, onAnalyze }) {
  const count = photos.length
  const photosOk = count >= MIN_IMAGES
  const profileFields = [patient.age, patient.sex, patient.region].filter(Boolean).length
  const modelDown = healthError || (health && !health.model?.loaded)

  return (
    <aside className="aside">
      <section className="card">
        <div className="card-head">
          <div className="card-title">
            <div className="card-icon">
              <Icon name="clipboard" />
            </div>
            <div>
              <h2>Screening summary</h2>
              <p>{analyzing ? 'Analysis in progress' : 'Review before analysing'}</p>
            </div>
          </div>
        </div>
        <div className="card-body">
          {analyzing ? (
            <AnalyzingSteps />
          ) : (
            <ul className="checklist">
              <li className={photosOk ? 'ok' : ''}>
                <span className="check-dot">
                  <Icon name="check" size={12} strokeWidth={3} />
                </span>
                Eye photos
                <span className="val num">
                  {count} / {MAX_IMAGES}
                  {!photosOk && ` · need ${MIN_IMAGES - count} more`}
                </span>
              </li>
              <li className={profileFields > 0 ? 'ok' : ''}>
                <span className="check-dot">
                  <Icon name="check" size={12} strokeWidth={3} />
                </span>
                Patient profile
                <span className="val">{profileFields > 0 ? `${profileFields} of 3 fields` : 'Optional'}</span>
              </li>
              <li className={patient.symptoms.length ? 'ok' : ''}>
                <span className="check-dot">
                  <Icon name="check" size={12} strokeWidth={3} />
                </span>
                Symptoms
                <span className="val">{patient.symptoms.length ? `${patient.symptoms.length} selected` : 'None'}</span>
              </li>
            </ul>
          )}
        </div>
        <div className="summary-foot">
          <button className="btn btn-primary btn-lg btn-block" disabled={!canAnalyze} onClick={onAnalyze}>
            {analyzing ? (
              <>
                <span className="spinner" /> Analysing {count} photos…
              </>
            ) : (
              <>
                Run screening <Icon name="arrowRight" size={16} />
              </>
            )}
          </button>
          <p className="hint">Results in a few seconds · photos are not stored</p>
        </div>
      </section>

      {modelDown && (
        <div className="alert alert-warn">
          <Icon name="alert" />
          <div>
            <div className="alert-title">{healthError ? 'API unreachable' : 'Screening model offline'}</div>
            <p className="small">
              {healthError ||
                health.model?.reason_not_loaded ||
                'The CNN could not be loaded on the server.'}
            </p>
          </div>
        </div>
      )}

      {health && (
        <section className="card system-card">
          <div className="system-row">
            <span>Model</span>
            <strong title={health.model?.name || ''}>{health.model?.name || 'Not loaded'}</strong>
          </div>
          <div className="system-row">
            <span>Architecture</span>
            <strong>
              {health.metrics?.variant ? `Variant ${health.metrics.variant} · ${health.metrics.head}` : '—'}
            </strong>
          </div>
          <div className="system-row">
            <span>Diet engine</span>
            <strong>{health.llm?.configured ? `${health.llm.n_models} LLMs (fallback)` : 'Rule-based only'}</strong>
          </div>
        </section>
      )}
    </aside>
  )
}

export default function App() {
  const [health, setHealth] = useState(null)
  const [healthError, setHealthError] = useState(null)
  const [symptomCatalog, setSymptomCatalog] = useState([])

  const [photos, setPhotos] = useState([]) // [{id, file, url}]
  const [patient, setPatient] = useState(EMPTY_PATIENT)

  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [diet, setDiet] = useState({ status: 'idle' })

  useEffect(() => {
    getHealth().then(setHealth).catch((e) => setHealthError(e.message))
    getSymptoms().then(setSymptomCatalog).catch(() => {})
  }, [])

  const count = photos.length
  const canAnalyze = count >= MIN_IMAGES && count <= MAX_IMAGES && !analyzing

  async function analyze() {
    setAnalyzing(true)
    setError(null)
    setResult(null)
    setDiet({ status: 'idle' })
    const ctx = toUserContext(patient)
    try {
      const res = await screenBatch(photos.map((p) => p.file), ctx)
      setResult({ ...res, userContext: ctx })
      window.scrollTo({ top: 0, behavior: 'smooth' })
      requestDiet(res.aggregate, ctx)
    } catch (e) {
      setError(e)
    } finally {
      setAnalyzing(false)
    }
  }

  async function requestDiet(aggregate, ctx) {
    setDiet({ status: 'loading' })
    try {
      const res = await getDietRecommendations(aggregate, ctx)
      setDiet({ status: 'ok', ...res })
    } catch (e) {
      setDiet({ status: 'error', message: e.message })
    }
  }

  function startOver() {
    photos.forEach((p) => URL.revokeObjectURL(p.url))
    setPhotos([])
    setPatient(EMPTY_PATIENT)
    setResult(null)
    setError(null)
    setDiet({ status: 'idle' })
  }

  const step = result ? 2 : count >= MIN_IMAGES ? 1 : 0

  return (
    <div className="app">
      <Header health={health} healthError={healthError} />

      <main className="container">
        <Stepper step={step} />
        {result ? (
          <Results
            result={result}
            photos={photos}
            diet={diet}
            onRetryDiet={() => requestDiet(result.aggregate, result.userContext)}
            onEdit={() => setResult(null)}
            onStartOver={startOver}
          />
        ) : (
          <>
            <Hero health={health} />
            <div className="layout">
              <div className="stack">
                {error && (
                  <div className="alert alert-error" role="alert">
                    <Icon name="alert" size={20} />
                    <div>
                      <div className="alert-title">Analysis failed</div>
                      <p>{error.message}</p>
                      {error.body?.detail?.per_image && (
                        <ul>
                          {error.body.detail.per_image
                            .filter((r) => r.error)
                            .map((r) => (
                              <li key={r.index}>
                                {r.filename}: {r.error}
                              </li>
                            ))}
                        </ul>
                      )}
                    </div>
                  </div>
                )}
                <PhotoUploader photos={photos} setPhotos={setPhotos} disabled={analyzing} />
                <PatientForm
                  patient={patient}
                  setPatient={setPatient}
                  symptomCatalog={symptomCatalog}
                  disabled={analyzing}
                />
              </div>
              <SummaryPanel
                photos={photos}
                patient={patient}
                health={health}
                healthError={healthError}
                analyzing={analyzing}
                canAnalyze={canAnalyze}
                onAnalyze={analyze}
              />
            </div>
          </>
        )}
      </main>

      <footer className="footer">
        <div className="container footer-inner">
          <span>HemoSense AI — a screening aid, not a medical device. Always confirm with a blood test.</span>
          <span>Fuzzy-logic colour correction · CNN regression · LLM dietary guidance</span>
        </div>
      </footer>
    </div>
  )
}
