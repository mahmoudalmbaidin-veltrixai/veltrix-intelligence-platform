import js from '@eslint/js'
import ts from 'typescript-eslint'
import vue from 'eslint-plugin-vue'

export default ts.config(
  {
    ignores: [
      'apps/**',
      'dist/**',
      'node_modules/**',
      'playwright-report/**',
      'test-results/**',
      '.codex-runtime/**',
      '*.config.ts',
      '*.config.js',
      // Local certification/evidence artifacts must not gate application lint.
      'VIP_*_EVIDENCE/**',
      'VIP_TEST_EVIDENCE/**',
      'VIP_BUG_EVIDENCE/**',
      'VIP_FINAL_RECERTIFICATION_EVIDENCE/**',
      'outputs/**',
      'reports/**',
      'docs/qa/platform-capability-and-uat/**',
      'artifacts/**',
    ],
  },
  js.configs.recommended,
  ...ts.configs.recommended,
  ...vue.configs['flat/recommended'],
  {
    files: ['**/*.vue'],
    languageOptions: {
      parserOptions: { parser: ts.parser },
    },
  },
  {
    rules: {
      'vue/multi-word-component-names': 'off',
      'vue/no-v-html': 'off',
      // Vue-2-only rule; false-positives on TypeScript union types (`a | b`)
      // inside template bindings (e.g. `x as 'a' | 'b'`).
      'vue/no-deprecated-filter': 'off',
      'vue/require-default-prop': 'off',
      'vue/attribute-hyphenation': 'off',
      // Editor engines are composables passed to studio components as a prop and
      // mutated through their own reactive state by design.
      'vue/no-mutating-props': 'off',
      // Purely stylistic formatting rules — handled by Prettier, not lint.
      'vue/max-attributes-per-line': 'off',
      'vue/singleline-html-element-content-newline': 'off',
      'vue/html-self-closing': 'off',
      'vue/html-indent': 'off',
      'vue/html-closing-bracket-newline': 'off',
      'vue/first-attribute-linebreak': 'off',
      'vue/attributes-order': 'off',
      'vue/html-closing-bracket-spacing': 'off',
      'vue/multiline-html-element-content-newline': 'off',
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    },
  },
)
