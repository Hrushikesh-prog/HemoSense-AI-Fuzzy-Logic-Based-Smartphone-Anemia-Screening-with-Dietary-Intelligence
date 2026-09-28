// Horizontal hemoglobin scale with the same severity bands the model uses
// (scratch/evaluate.py: <=7 Severe, <=10 Moderate, <=12 Mild, >12 Normal).
const SCALE_MIN = 4
const SCALE_MAX = 18
const BANDS = [
  { name: 'Severe', from: SCALE_MIN, to: 7, cls: 'severe' },
  { name: 'Moderate', from: 7, to: 10, cls: 'moderate' },
  { name: 'Mild', from: 10, to: 12, cls: 'mild' },
  { name: 'Normal', from: 12, to: SCALE_MAX, cls: 'normal' },
]

const pos = (v) => ((Math.min(Math.max(v, SCALE_MIN), SCALE_MAX) - SCALE_MIN) / (SCALE_MAX - SCALE_MIN)) * 100

export default function HbGauge({ value, min, max }) {
  return (
    <div className="gauge" role="img" aria-label={`Hemoglobin ${value.toFixed(1)} g/dL`}>
      <div className="gauge-track">
        {BANDS.map((b) => (
          <div key={b.name} className={`gauge-band band-${b.cls}`} style={{ width: `${pos(b.to) - pos(b.from)}%` }} />
        ))}
        {min != null && max != null && max > min && (
          <div className="gauge-range" style={{ left: `${pos(min)}%`, width: `${pos(max) - pos(min)}%` }} />
        )}
        <div className="gauge-marker" style={{ left: `${pos(value)}%` }}>
          <span>{value.toFixed(1)} g/dL</span>
        </div>
      </div>
      <div className="gauge-labels">
        {[7, 10, 12].map((t) => (
          <span key={t} className="tick" style={{ left: `${pos(t)}%` }}>
            {t}
          </span>
        ))}
        {BANDS.map((b) => (
          <span key={b.name} className="name" style={{ left: `${(pos(b.from) + pos(b.to)) / 2}%` }}>
            {b.name}
          </span>
        ))}
      </div>
      <p className="gauge-caption">
        Severity bands used by the model (g/dL). Outlined region shows the spread across your photos.
      </p>
    </div>
  )
}
