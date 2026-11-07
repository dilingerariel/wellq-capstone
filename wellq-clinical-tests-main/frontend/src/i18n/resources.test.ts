import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { it, expect } from 'vitest'
it.each(['es', 'en'])(
  'translation keys remain unique in %s without overwriting existing screens',
  (language) => {
    const text = readFileSync(
      join(dirname(fileURLToPath(import.meta.url)), `${language}.json`),
      'utf8',
    )
    const keys = [...text.matchAll(/^ {2}"([^"]+)":/gm)].map((match) => match[1])
    expect(keys.length).toBeGreaterThan(0)
    expect(keys.filter((key, index) => keys.indexOf(key) !== index)).toEqual([])
  },
)
