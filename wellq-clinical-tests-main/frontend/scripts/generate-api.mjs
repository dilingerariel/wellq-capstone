import { readFileSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
const source = readFileSync(new URL('../../backend/docs/openapi.json', import.meta.url), 'utf8')
  .replace(/^\uFEFF/, '')
  .replace(/\r\n/g, '\n')
const spec = JSON.parse(source)
function type(s) {
  if (!s || Object.keys(s).length === 0) return 'unknown'
  if (s.$ref) return s.$ref.split('/').at(-1)
  if (s.enum) return s.enum.map((v) => JSON.stringify(v)).join(' | ')
  if (s.anyOf || s.oneOf) return (s.anyOf || s.oneOf).map(type).join(' | ')
  if (s.allOf) return s.allOf.map(type).join(' & ')
  if (s.type === 'array') return `Array<${type(s.items)}>`
  if (s.type === 'object' || s.properties) {
    const fields = Object.entries(s.properties || {}).map(
      ([k, v]) => `${JSON.stringify(k)}${(s.required || []).includes(k) ? '' : '?'}: ${type(v)}`,
    )
    if (s.additionalProperties)
      fields.push(
        `[key: string]: ${s.additionalProperties === true ? 'unknown' : type(s.additionalProperties)}`,
      )
    return fields.length ? `{ ${fields.join('; ')} }` : 'Record<string, unknown>'
  }
  return (
    { string: 'string', integer: 'number', number: 'number', boolean: 'boolean', null: 'null' }[
      s.type
    ] || 'unknown'
  )
}
const generated =
  '// Generated from backend/docs/openapi.json. Do not edit.\n' +
  `// Source SHA-256: ${createHash('sha256').update(source).digest('hex')}\n` +
  Object.entries(spec.components.schemas)
    .map(([name, s]) => `export type ${name} = ${type(s)}\n`)
    .join('\n')
const target = new URL('../src/types/api.generated.ts', import.meta.url)
if (process.argv.includes('--check')) {
  if (readFileSync(target, 'utf8').replace(/\r\n/g, '\n') !== generated)
    throw new Error('OpenAPI types changed: run npm run contracts:generate')
  console.log('OpenAPI types match the backend specification')
} else writeFileSync(target, generated)
