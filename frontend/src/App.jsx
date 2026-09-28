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

  return (
    <div className="app">
      <Header health={health} healthError={healthError} />

      <main className="container">
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
            <section className="intro">
              <h1>Anemia screening from eye photos</h1>
              <p>
                Upload {MIN_IMAGES}–{MAX_IMAGES} photos of the lower eyelid (conjunctiva). Each photo
                is colour-corrected with fuzzy logic, analysed by the CNN, and the results are
                combined into one hemoglobin estimate with symptoms and a recovery diet.
              </p>
            </section>

            <PhotoUploader photos={photos} setPhotos={setPhotos} disabled={analyzing} />

            <PatientForm
              patient={patient}
              setPatient={setPatient}
              symptomCatalog={symptomCatalog}
              disabled={analyzing}
            />

            {error && (
              <div className="alert alert-error" role="alert">
                <strong>Analysis failed.</strong> {error.message}
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
            )}

            <div className="actions sticky-actions">
              <span className="muted">
                {count < MIN_IMAGES
                  ? `Add at least ${MIN_IMAGES - count} more photo${MIN_IMAGES - count > 1 ? 's' : ''}`
                  : `${count} photo${count > 1 ? 's' : ''} ready`}
              </span>
              <button className="btn btn-primary" disabled={!canAnalyze} onClick={analyze}>
                {analyzing ? (
                  <>
                    <span className="spinner" /> Analysing {count} photos…
                  </>
                ) : (
                  'Analyse photos'
                )}
              </button>
            </div>
          </>
        )}
      </main>

      <footer className="footer">
        HemoSense AI is a screening aid, not a medical device. Always confirm with a blood test.
      </footer>
    </div>
  )
}
