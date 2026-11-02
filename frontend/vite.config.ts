import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev: run the API with `AUTOBETS_MODE=demo uvicorn --factory autobets.api.app:create_app` and `npm run dev`.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
  test: { environment: 'node' },
})
