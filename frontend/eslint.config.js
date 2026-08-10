import js from '@eslint/js';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import tsParser from '@typescript-eslint/parser';
import prettier from 'eslint-config-prettier';
import svelte from 'eslint-plugin-svelte';

const typescriptRecommendedRules =
  tsPlugin.configs['flat/recommended'].find(
    (config) => config.name === 'typescript-eslint/recommended'
  )?.rules ?? {};

export default [
  {
    name: 'gestiona-sv/ignores',
    ignores: [
      '.pnpm-store/**',
      '.svelte-kit/**',
      'build/**',
      'coverage/**',
      'node_modules/**',
      'playwright-report/**',
      'static/**',
      'test-results/**'
    ]
  },
  {
    ...js.configs.recommended,
    name: 'gestiona-sv/javascript-recommended'
  },
  ...tsPlugin.configs['flat/recommended'],
  ...svelte.configs['flat/recommended'],
  ...svelte.configs['flat/prettier'],
  {
    name: 'gestiona-sv/svelte-typescript',
    files: ['**/*.svelte'],
    languageOptions: {
      parserOptions: {
        parser: tsParser
      }
    },
    rules: {
      ...typescriptRecommendedRules,
      // TypeScript and svelte-check resolve identifiers inside component scripts.
      'no-undef': 'off'
    }
  },
  {
    name: 'gestiona-sv/runtime-map-adapter',
    files: [
      'src/lib/features/branches/components/BranchLocationPicker.svelte',
      'src/lib/features/branches/components/BranchMap.svelte',
      'src/lib/features/branches/components/BranchMiniMap.svelte',
      'src/lib/services/maps.ts'
    ],
    rules: {
      // The map adapter integrates a runtime-loaded third-party API whose
      // ambient types are not bundled yet. Keep the exception tightly scoped.
      '@typescript-eslint/no-explicit-any': 'off'
    }
  },
  {
    name: 'gestiona-sv/unused-arguments',
    files: ['**/*.{ts,svelte}'],
    rules: {
      '@typescript-eslint/no-unused-vars': [
        'error',
        {
          argsIgnorePattern: '^_',
          caughtErrorsIgnorePattern: '^_',
          varsIgnorePattern: '^_'
        }
      ]
    }
  },
  {
    ...prettier,
    name: 'gestiona-sv/prettier-compatibility'
  }
];
