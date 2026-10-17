import {defineConfig} from 'vitest/config';
export default defineConfig({
  test: {
    environment: 'node', include: ['tests/policy-activation-client.test.ts'],
    passWithNoTests: false, reporters: ['default', 'junit'],
    outputFile: {junit: 'test-results/policy-activation-client.xml'},
  },
});
