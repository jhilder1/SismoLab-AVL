import { useEffect, useState } from 'react'

// El backend corre en otro puerto durante el desarrollo. Por eso main.py
// tiene CORS habilitado para localhost:5173.
const API = 'http://127.0.0.1:8000'

function App() {
  const [estado, setEstado] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(`${API}/health`)
      .then((r) => r.json())
      .then(setEstado)
      .catch((e) => setError(e.message))
  }, [])

  return (
    <div style={{ fontFamily: 'system-ui', padding: '2rem' }}>
      <h1>SismoLab AVL</h1>
      {error && <p style={{ color: 'crimson' }}>Sin conexión: {error}</p>}
      {estado && <p style={{ color: 'green' }}>Backend conectado: {estado.status}</p>}
      {!estado && !error && <p>Conectando…</p>}
    </div>
  )
}

export default App