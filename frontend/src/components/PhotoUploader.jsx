import { useRef, useState } from 'react'
import { MAX_IMAGES, MIN_IMAGES } from '../api.js'

const ACCEPTED = ['image/jpeg', 'image/png', 'image/webp', 'image/bmp']
const MAX_MB = 10

let nextId = 1

export default function PhotoUploader({ photos, setPhotos, disabled }) {
  const fileInput = useRef(null)
  const cameraInput = useRef(null)
  const [dragging, setDragging] = useState(false)
  const [notice, setNotice] = useState(null)

  function addFiles(fileList) {
    const incoming = Array.from(fileList || [])
    const rejected = []
    const accepted = []
    for (const f of incoming) {
      if (!ACCEPTED.includes(f.type)) rejected.push(`${f.name}: unsupported format`)
      else if (f.size > MAX_MB * 1024 * 1024) rejected.push(`${f.name}: larger than ${MAX_MB} MB`)
      else accepted.push(f)
    }
    const room = MAX_IMAGES - photos.length
    if (accepted.length > room) {
      rejected.push(`Only ${MAX_IMAGES} photos allowed — ${accepted.length - room} skipped`)
    }
    const added = accepted.slice(0, Math.max(room, 0)).map((file) => ({
      id: nextId++,
      file,
      url: URL.createObjectURL(file),
    }))
    if (added.length) setPhotos((prev) => [...prev, ...added])
    setNotice(rejected.length ? rejected.join(' · ') : null)
  }

  function remove(id) {
    setPhotos((prev) => {
      const p = prev.find((x) => x.id === id)
      if (p) URL.revokeObjectURL(p.url)
      return prev.filter((x) => x.id !== id)
    })
  }

  const full = photos.length >= MAX_IMAGES
  const pct = Math.min(100, (photos.length / MAX_IMAGES) * 100)

  return (
    <section className="card">
      <div className="card-head">
        <h2>
          <span className="step">1</span> Eye photos
        </h2>
        <span className={`counter ${photos.length >= MIN_IMAGES ? 'ok' : ''}`}>
          {photos.length} / {MAX_IMAGES}
        </span>
      </div>
      <div className="progress" aria-hidden="true">
        <div className="progress-bar" style={{ width: `${pct}%` }} />
        <div className="progress-min" style={{ left: `${(MIN_IMAGES / MAX_IMAGES) * 100}%` }} />
      </div>

      <div
        className={`dropzone ${dragging ? 'dragging' : ''} ${full || disabled ? 'disabled' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          if (!full && !disabled) setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          if (!full && !disabled) addFiles(e.dataTransfer.files)
        }}
      >
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"
            stroke="currentColor"
            strokeWidth="1.6"
          />
          <circle cx="12" cy="12" r="3.2" stroke="currentColor" strokeWidth="1.6" />
        </svg>
        <p>
          <strong>Drag & drop</strong> eye photos here
        </p>
        <div className="dropzone-buttons">
          <button
            type="button"
            className="btn"
            disabled={full || disabled}
            onClick={() => fileInput.current?.click()}
          >
            Choose files
          </button>
          <button
            type="button"
            className="btn"
            disabled={full || disabled}
            onClick={() => cameraInput.current?.click()}
          >
            Take photo
          </button>
        </div>
        <p className="muted small">
          JPG, PNG, WEBP or BMP · up to {MAX_MB} MB each · {MIN_IMAGES}–{MAX_IMAGES} photos
        </p>
        <input
          ref={fileInput}
          type="file"
          accept={ACCEPTED.join(',')}
          multiple
          hidden
          onChange={(e) => {
            addFiles(e.target.files)
            e.target.value = ''
          }}
        />
        <input
          ref={cameraInput}
          type="file"
          accept="image/*"
          capture="environment"
          hidden
          onChange={(e) => {
            addFiles(e.target.files)
            e.target.value = ''
          }}
        />
      </div>

      {notice && <div className="alert alert-warn small">{notice}</div>}

      {photos.length > 0 && (
        <ul className="thumbs">
          {photos.map((p, i) => (
            <li key={p.id} className="thumb">
              <img src={p.url} alt={`Eye photo ${i + 1}`} />
              <span className="thumb-index">{i + 1}</span>
              {!disabled && (
                <button
                  type="button"
                  className="thumb-remove"
                  aria-label={`Remove photo ${i + 1}`}
                  onClick={() => remove(p.id)}
                >
                  ×
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      <details className="tips">
        <summary>Tips for a good photo</summary>
        <ul>
          <li>Use natural daylight or bright, even indoor light — avoid coloured light.</li>
          <li>Gently pull the lower eyelid down so the pink inner lining is visible.</li>
          <li>Hold the phone 10–15 cm away and keep it steady; no filters or flash glare.</li>
          <li>Take photos of both eyes, from slightly different angles, for a stronger result.</li>
        </ul>
      </details>
    </section>
  )
}
