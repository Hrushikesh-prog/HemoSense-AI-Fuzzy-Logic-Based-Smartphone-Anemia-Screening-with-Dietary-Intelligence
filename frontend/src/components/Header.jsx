export default function Header({ health, healthError }) {
  let status = { cls: 'pending', text: 'Connecting…' }
  if (healthError) status = { cls: 'down', text: 'API offline' }
  else if (health) {
    status = health.model?.loaded
      ? { cls: 'up', text: 'Model ready' }
      : { cls: 'warn', text: 'Model not loaded' }
  }
  const title = healthError || health?.model?.reason_not_loaded || health?.model?.name || ''

  return (
    <header className="header">
      <div className="container header-inner">
        <div className="brand">
          <img src="/favicon.svg" alt="" width="28" height="28" />
          <span>
            HemoSense <strong>AI</strong>
          </span>
        </div>
        <div className="header-status">
          <span className={`status status-${status.cls}`} title={title}>
            <span className="dot" /> {status.text}
          </span>
          {health && (
            <span
              className={`status status-${health.llm?.configured ? 'up' : 'warn'}`}
              title={health.llm?.configured ? 'OpenRouter key configured' : 'OPENROUTER_API_KEY not set'}
            >
              <span className="dot" /> {health.llm?.configured ? 'AI diet on' : 'AI diet off'}
            </span>
          )}
        </div>
      </div>
    </header>
  )
}
