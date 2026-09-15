import { useEffect, useState } from 'react'

const API = 'http://127.0.0.1:8000'

function App() {
  const [estado, setEstado] = useState(null)
  const [error, setError] = useState(null)

  // Trae el escenario completo. Cada operación que modifique algo devolverá
  // esta misma forma, así que la pantalla se repinta con una sola respuesta.
  const cargar = () => {
    fetch(`${API}/state`)
      .then((r) => r.json())
      .then((d) => { setEstado(d); setError(null) })
      .catch((e) => setError(e.message))
  }

  useEffect(cargar, [])

  if (error) return <Marco><p style={{ color: 'crimson' }}>Sin conexión: {error}</p></Marco>
  if (!estado) return <Marco><p>Cargando…</p></Marco>

  return (
    <Marco>
      <button onClick={cargar} style={{ marginBottom: '1.5rem' }}>Actualizar</button>

      <Bloque titulo="Catálogo">
        <Dato etiqueta="Activos" valor={estado.counts.active} />
        <Dato etiqueta="Archivados" valor={estado.counts.archived} />
        <Dato etiqueta="Eliminados" valor={estado.counts.deleted} />
        <Dato etiqueta="Reportes en cola" valor={estado.counts.queued_reports} />
        <Dato etiqueta="Acciones deshacibles" valor={estado.counts.undo_depth} />
      </Bloque>

      <Bloque titulo="Árbol AVL">
        <Dato etiqueta="Altura" valor={estado.tree.height} />
        <Dato etiqueta="Hojas" valor={estado.tree.leaves} />
        <Dato etiqueta="Raíz" valor={estado.tree.root ?? '—'} />
        <Dato etiqueta="Balanceado" valor={estado.tree.balanced ? 'sí' : 'NO'} />
        <Dato etiqueta="Modo" valor={estado.stress_mode ? 'ESTRÉS' : 'normal'} />
      </Bloque>

      <Bloque titulo="Rotaciones">
        <Dato etiqueta="LL" valor={estado.rotations.ll} />
        <Dato etiqueta="RR" valor={estado.rotations.rr} />
        <Dato etiqueta="LR" valor={estado.rotations.lr} />
        <Dato etiqueta="RL" valor={estado.rotations.rl} />
        <Dato etiqueta="Giros izq." valor={estado.rotations.simple_left} />
        <Dato etiqueta="Giros der." valor={estado.rotations.simple_right} />
      </Bloque>

      <Bloque titulo="Parámetros">
        <Dato etiqueta="W (horas)" valor={estado.parameters.W_hours} />
        <Dato etiqueta="R (km)" valor={estado.parameters.R_km} />
        <Dato etiqueta="L (profundidad)" valor={estado.parameters.L_depth} />
        <Dato etiqueta="T (horas)" valor={estado.parameters.T_archive_hours} />
        <Dato etiqueta="Reloj" valor={estado.clock.replace('T', ' ')} />
      </Bloque>
    </Marco>
  )
}

function Marco({ children }) {
  return (
    <div style={{ fontFamily: 'system-ui', padding: '2rem', maxWidth: 900 }}>
      <h1 style={{ marginTop: 0 }}>SismoLab AVL</h1>
      {children}
    </div>
  )
}

function Bloque({ titulo, children }) {
  return (
    <section style={{ marginBottom: '1.5rem' }}>
      <h2 style={{ fontSize: '1rem', textTransform: 'uppercase', color: '#666' }}>{titulo}</h2>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1.5rem' }}>{children}</div>
    </section>
  )
}

function Dato({ etiqueta, valor }) {
  return (
    <div>
      <div style={{ fontSize: '0.75rem', color: '#888' }}>{etiqueta}</div>
      <div style={{ fontSize: '1.25rem', fontVariantNumeric: 'tabular-nums' }}>{valor}</div>
    </div>
  )
}

export default App