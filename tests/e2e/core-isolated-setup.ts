export default function requireOwnedCoreTarget(): void {
  if (!process.env.BUYEROS_POLICY_TARGET_RECEIPT || !process.env.BUYEROS_TEST_DATABASE_URL) {
    throw new Error('Use services/api/tools/run_core_isolated.py to allocate and verify this run\'s disposable target');
  }
}
