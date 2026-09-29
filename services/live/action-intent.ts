/** One key and one inflight promise per exact action payload. No browser storage. */
export class ActionIntent<T> {
  private current: {fingerprint: string; key: string; promise: Promise<T> | null} | null = null;
  constructor(private readonly newKey: () => string = () => crypto.randomUUID()) {}

  run(fingerprint: string, work: (key: string) => Promise<T>): Promise<T> {
    if (!fingerprint) throw new Error('Action fingerprint required');
    if (!this.current || this.current.fingerprint !== fingerprint) {
      this.current = {fingerprint, key: this.newKey(), promise: null};
    }
    const action = this.current;
    if (action.promise) return action.promise;
    const promise = Promise.resolve().then(() => work(action.key));
    action.promise = promise;
    void promise.then(
      () => {if (this.current === action) this.current = null;},
      () => {if (this.current === action) action.promise = null;},
    );
    return promise;
  }
}
