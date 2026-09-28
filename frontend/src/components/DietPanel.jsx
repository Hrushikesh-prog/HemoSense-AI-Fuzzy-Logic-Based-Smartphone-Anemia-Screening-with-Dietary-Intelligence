import ReactMarkdown from 'react-markdown'

function List({ title, items }) {
  if (!items?.length) return null
  return (
    <div className="diet-block">
      <h3 className="subhead">{title}</h3>
      <ul>
        {items.map((i) => (
          <li key={i}>{i}</li>
        ))}
      </ul>
    </div>
  )
}

export default function DietPanel({ plan, diet, onRetry }) {
  return (
    <section className="card">
      <div className="card-head">
        <h2>Recovery diet plan</h2>
        <span className="muted small">{plan.diet_type} diet</span>
      </div>
      <p className="diet-goal">{plan.goal}</p>

      <div className="diet-grid">
        <List title="Iron-rich foods to prioritise" items={plan.iron_rich_foods} />
        <List title="Pair with vitamin C" items={plan.pair_with_vitamin_c} />
        <List title="Avoid or limit" items={plan.avoid_or_limit} />
        <List title="Extra tips for you" items={plan.extra_tips} />
      </div>

      {Object.keys(plan.sample_day || {}).length > 0 && (
        <div className="diet-block">
          <h3 className="subhead">Sample day</h3>
          <table className="meal-table">
            <tbody>
              {Object.entries(plan.sample_day).map(([meal, text]) => (
                <tr key={meal}>
                  <th>{meal}</th>
                  <td>{text}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="diet-callouts">
        <div className="callout">
          <strong>When to see a clinician</strong>
          <p>{plan.when_to_see_clinician}</p>
        </div>
        <div className="callout">
          <strong>Recovery outlook</strong>
          <p>{plan.recovery_outlook}</p>
        </div>
      </div>

      <div className="ai-diet">
        <div className="card-head">
          <h3>AI-personalised recommendations</h3>
          {diet.status === 'ok' && <span className="muted small">via {diet.model_used}</span>}
        </div>
        {diet.status === 'loading' && (
          <p className="muted">
            <span className="spinner dark" /> Generating a plan tailored to your result and details…
          </p>
        )}
        {diet.status === 'error' && (
          <div className="alert alert-warn small">
            AI recommendations are unavailable right now ({diet.message}). The plan above still
            applies.{' '}
            <button className="link" onClick={onRetry}>
              Try again
            </button>
          </div>
        )}
        {diet.status === 'ok' && (
          <div className="markdown">
            <ReactMarkdown>{diet.recommendations}</ReactMarkdown>
          </div>
        )}
      </div>
    </section>
  )
}
