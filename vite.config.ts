import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const tilesRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), 'tiles')

function serveOfflineTiles(): Plugin {
  const attach = (server: { middlewares: { use: (path: string, fn: Function) => void } }) => {
    server.middlewares.use('/tiles', (req: { url?: string }, res: any, next: () => void) => {
      const rel = decodeURIComponent((req.url || '').split('?')[0]).replace(/^\/+/, '')
      if (!rel || rel.includes('..')) {
        next()
        return
      }
      const file = path.resolve(tilesRoot, rel)
      const safe = path.relative(tilesRoot, file)
      if (safe.startsWith('..') || path.isAbsolute(safe)) {
        res.statusCode = 403
        res.end()
        return
      }
      fs.stat(file, (err, st) => {
        if (err || !st.isFile()) {
          res.statusCode = 404
          res.end()
          return
        }
        res.setHeader('Content-Type', 'image/png')
        res.setHeader('Cache-Control', 'public, max-age=86400')
        fs.createReadStream(file).pipe(res)
      })
    })
  }
  return {
    name: 'serve-offline-tiles',
    configureServer: attach,
    configurePreviewServer: attach,
  }
}

export default defineConfig({
  plugins: [react(), serveOfflineTiles()],
  server: {
    host: true,
    port: 5173,
    watch: {
      ignored: ['**/tiles/**'],
    },
  },
})
