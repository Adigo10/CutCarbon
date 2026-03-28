import {
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type PropsWithChildren,
  useEffect,
  useEffectEvent,
  useRef,
  useState,
} from 'react'
import type { Chart, ChartConfiguration } from 'chart.js'
import type { Toast } from '../types'
import { cn } from '../lib/format'

type MermaidApi = typeof import('mermaid').default

let mermaidReady = false
let mermaidApi: MermaidApi | null = null

async function ensureMermaid() {
  if (mermaidApi) return mermaidApi
  const module = await import('mermaid')
  mermaidApi = module.default

  if (!mermaidReady) {
    mermaidApi.initialize({
      startOnLoad: false,
      securityLevel: 'loose',
      theme: 'neutral',
      fontFamily: 'Plus Jakarta Sans, sans-serif',
    })
    mermaidReady = true
  }

  return mermaidApi
}

interface GlyphProps {
  label: string
  tone?: 'forest' | 'cyan' | 'amber' | 'rose' | 'slate'
  small?: boolean
}

export function Glyph({ label, tone = 'forest', small = false }: GlyphProps) {
  return (
    <span className={cn('glyph', `glyph-${tone}`, small && 'glyph-small')}>
      {label.slice(0, 2).toUpperCase()}
    </span>
  )
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  tone?: 'primary' | 'ghost' | 'soft' | 'danger'
  busy?: boolean
}

export function Button({
  children,
  className,
  tone = 'ghost',
  busy = false,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn('button', `button-${tone}`, className)}
      disabled={disabled || busy}
      {...props}
    >
      {busy ? <span className="button-spinner" aria-hidden="true" /> : null}
      <span>{children}</span>
    </button>
  )
}

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: 'fresh' | 'cyan' | 'amber' | 'rose' | 'neutral'
}

export function Badge({ children, className, tone = 'neutral', ...props }: BadgeProps) {
  return (
    <span className={cn('badge', `badge-${tone}`, className)} {...props}>
      {children}
    </span>
  )
}

interface PanelProps extends PropsWithChildren {
  className?: string
}

export function Panel({ children, className }: PanelProps) {
  return <section className={cn('panel', className)}>{children}</section>
}

interface MetricCardProps {
  eyebrow: string
  value: string
  detail: string
  tone?: 'fresh' | 'cyan' | 'amber' | 'rose'
}

export function MetricCard({ eyebrow, value, detail, tone = 'fresh' }: MetricCardProps) {
  return (
    <div className={cn('metric-card', `metric-card-${tone}`)}>
      <span className="metric-eyebrow">{eyebrow}</span>
      <strong className="metric-value">{value}</strong>
      <span className="metric-detail">{detail}</span>
    </div>
  )
}

interface ChartSurfaceProps {
  config: ChartConfiguration | null
  empty: string
  height?: number
}

export function ChartSurface({ config, empty, height = 280 }: ChartSurfaceProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    if (!canvasRef.current || !config) return undefined
    let active = true
    let chart: Chart | null = null

    import('chart.js/auto').then(({ Chart: ChartJS }) => {
      if (!active || !canvasRef.current) return
      chart = new ChartJS(canvasRef.current, config)
    })

    return () => {
      active = false
      chart?.destroy()
    }
  }, [config])

  if (!config) {
    return <div className="empty-copy">{empty}</div>
  }

  return (
    <div className="chart-wrap" style={{ minHeight: height }}>
      <canvas ref={canvasRef} />
    </div>
  )
}

interface MermaidSurfaceProps {
  diagram: string
  empty: string
}

export function MermaidSurface({ diagram, empty }: MermaidSurfaceProps) {
  const [renderKey, setRenderKey] = useState(0)
  const hostRef = useRef<HTMLDivElement | null>(null)
  const rerenderOnResize = useEffectEvent(() => {
    setRenderKey((value) => value + 1)
  })

  useEffect(() => {
    window.addEventListener('resize', rerenderOnResize)
    return () => window.removeEventListener('resize', rerenderOnResize)
  }, [])

  useEffect(() => {
    if (!hostRef.current) return undefined
    if (!diagram) {
      hostRef.current.innerHTML = `<div class="empty-copy">${empty}</div>`
      return undefined
    }

    let active = true
    const id = `mermaid-${renderKey}-${Math.random().toString(36).slice(2, 8)}`

    ensureMermaid()
      .then((mermaid) => mermaid.render(id, diagram))
      .then(({ svg }) => {
        if (!active || !hostRef.current) return
        hostRef.current.innerHTML = svg
      })
      .catch(() => {
        if (!active || !hostRef.current) return
        hostRef.current.innerHTML = `<pre class="mermaid-fallback">${diagram}</pre>`
      })

    return () => {
      active = false
    }
  }, [diagram, empty, renderKey])

  return <div ref={hostRef} className="mermaid-wrap" />
}

export function EmptyState({
  title,
  body,
  className,
}: {
  title: string
  body: string
  className?: string
}) {
  return (
    <div className={cn('empty-state', className)}>
      <Glyph label={title} tone="forest" />
      <h3>{title}</h3>
      <p>{body}</p>
    </div>
  )
}

export function ToastViewport({ toasts }: { toasts: Toast[] }) {
  if (!toasts.length) return null

  return (
    <div className="toast-stack" role="status" aria-live="polite">
      {toasts.map((toast) => (
        <div key={toast.id} className={cn('toast', `toast-${toast.tone}`)}>
          <span className="toast-dot" />
          <span>{toast.message}</span>
        </div>
      ))}
    </div>
  )
}
