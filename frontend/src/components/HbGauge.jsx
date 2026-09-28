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
    <div className="gauge" aria-label={`Hemoglobin ${value} g/dL`}>
      <div className="gauge-track">
        {BANDS.map((b) => (
          <div
            key={b.name}
            className={`gauge-band band-${b.cls}`}
            style={{ left: `${pos(b.from)}%`, width: `${pos(b.to) - pos(b.from)}%` }}
          >
            <span>{b.name}</span>
          </div>
        ))}
        {min != null && max != null && (
          <div className="gauge-range" style={{ left: `${pos(min)}%`, width: `${Math.max(pos(max) - pos(min), 0.5)}%` }} />
        )}
        <div className="gauge-marker" style={{ left: `${pos(value)}%` }}>
          <span>{value.toFixed(1)}</span>
        </div>
      </div>
      <div className="gauge-ticks">
        {[4, 7, 10, 12, 18].map((t) => (
          <span key={t} style={{ left: `${pos(t)}%` }}>
            {t}
          </span>
        ))}
      </div>
      <p className="muted small">Hemoglobin, g/dL · shaded bar shows the range across your photos</p>
    </div>
  )
}
