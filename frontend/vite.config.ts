import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = { ...loadEnv(mode, process.cwd(), 'VITE_'), ...process.env }
  const required = ['VITE_SUPABASE_URL', 'VITE_SUPABASE_PUBLISHABLE_KEY']
  const missing = required.filter((key) => !env[key]?.trim())

  if (missing.length > 0) {
    throw new Error(`Missing frontend environment variables: ${missing.join(', ')}`)
  }

  return {}
})
