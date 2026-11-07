import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import hooks from 'eslint-plugin-react-hooks'
import globals from 'globals'
export default tseslint.config(
  {
    files: ['scripts/service-worker.template.js'],
    languageOptions: { globals: { __CACHE_NAME__: 'readonly', __PUBLIC_ASSETS__: 'readonly' } },
  },
  { ignores: ['dist', 'node_modules', 'playwright-report', 'test-results'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx,js,mjs}'],
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
  },
  {
    files: ['**/*.tsx'],
    plugins: { 'react-hooks': hooks },
    rules: {
      ...hooks.configs.recommended.rules,
    },
  },
)
