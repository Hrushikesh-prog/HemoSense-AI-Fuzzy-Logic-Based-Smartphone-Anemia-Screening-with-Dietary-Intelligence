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
          <div className="brand-mark">
            <img src="/favicon.svg" alt="" />
          </div>
          <div>
            <div className="brand-name">
              HemoSense <span>AI</span>
            </div>
            <div className="brand-sub">Non-invasive anemia screening</div>
          </div>
        </div>
        <div className="header-status">
          <span className={`status status-${status.cls}`} title={title}>
            <span className="dot" /> {status.text}
          </span>
          {health && (
            <span
              className={`status status-llm status-${health.llm?.configured ? 'up' : 'warn'}`}
              title={health.llm?.configured ? 'OpenRouter key configured' : 'OPENROUTER_API_KEY not set'}
            >
              <span className="dot" /> {health.llm?.configured ? 'AI diet online' : 'AI diet offline'}
            </span>
          )}
        </div>
      </div>
    </header>
  )
}
