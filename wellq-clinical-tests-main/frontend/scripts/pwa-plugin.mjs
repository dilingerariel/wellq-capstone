import { readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { resolve, relative } from 'node:path'
import { createHash } from 'node:crypto'
export function shellPwa() {
  let directory
  return {
    name: 'wellq-static-shell-only',
    apply: 'build',
    configResolved(config) {
      directory = resolve(config.root, config.build.outDir)
    },
    closeBundle() {
      const files = readdirSync(directory, { recursive: true, withFileTypes: true })
        .filter((file) => file.isFile())
        .map((file) =>
          relative(directory, resolve(file.parentPath, file.name)).replaceAll('\\', '/'),
        )
        .filter(
          (file) =>
            file === 'index.html' ||
            file === 'manifest.webmanifest' ||
            file === 'wellq.svg' ||
            /^icons\/icon-\d+\.png$/.test(file) ||
            /^assets\/[\w.-]+\.(js|css)$/.test(file),
        )
        .sort()
      const version = createHash('sha256')
      for (const file of files) version.update(file).update(readFileSync(resolve(directory, file)))
      const template = readFileSync(
        new URL('./service-worker.template.js', import.meta.url),
        'utf8',
      )
      writeFileSync(
        resolve(directory, 'sw.js'),
        template
          .replace(
            '__CACHE_NAME__',
            JSON.stringify(`wellq-shell-${version.digest('hex').slice(0, 16)}`),
          )
          .replace('__PUBLIC_ASSETS__', JSON.stringify(files.map((file) => '/' + file))),
      )
    },
  }
}
