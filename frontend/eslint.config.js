import js from '@eslint/js'
import globals from 'globals'
import react from 'eslint-plugin-react'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'

export default [
  { ignores: ['dist'] },
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    settings: { react: { version: '18.3' } },
    plugins: {
      react,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...js.configs.recommended.rules,
      ...react.configs.recommended.rules,
      ...react.configs['jsx-runtime'].rules,
      ...reactHooks.configs.recommended.rules,
      'react/jsx-no-target-blank': 'off',
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
      // Multi-Country Phase 1 guardrail: keep all currency/locale formatting
      // routed through @/lib/format. Starts as 'warn' during the codemod sweep,
      // promoted to 'error' once every site is converted.
      'no-restricted-syntax': [
        'warn',
        {
          selector: "Literal[value=/₹/]",
          message: "Don't hardcode ₹. Use formatMoney() from @/lib/format.",
        },
        {
          selector: "CallExpression[callee.property.name='toLocaleString'][arguments.0.value='en-IN']",
          message: "Don't hardcode toLocaleString('en-IN'). Use formatNumber()/formatMoney() from @/lib/format.",
        },
        {
          selector: "CallExpression[callee.property.name='toLocaleDateString'][arguments.0.value='en-IN']",
          message: "Don't hardcode toLocaleDateString('en-IN'). Use formatDate() from @/lib/format.",
        },
      ],
    },
  },
  {
    // The formatter module legitimately contains the symbol and locale.
    files: ['src/lib/format.js'],
    rules: { 'no-restricted-syntax': 'off' },
  },
]
