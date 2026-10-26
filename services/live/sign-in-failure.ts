/** User-facing sign-in reasons. Provider bodies, URLs and tokens never enter these strings. */
export const signInReasons = [
  'credentials',
  'wrong_password',
  'unknown_email',
  'invalid_email',
  'validation',
  'network',
  'rate_limited',
  'service',
  'google_redirect',
  'stale_transaction',
  'forbidden',
  'unverified_email',
  'social_only',
  'callback',
  'session',
] as const;
export type SignInReason = typeof signInReasons[number];

const allowedCodes = new Set([
  'INVALID_EMAIL_OR_PASSWORD',
  'INVALID_CREDENTIALS',
  'INVALID_EMAIL',
  'INVALID_PASSWORD',
  'USER_NOT_FOUND',
  'USER_EMAIL_NOT_FOUND',
  'PASSWORD_TOO_SHORT',
  'PASSWORD_TOO_LONG',
  'EMAIL_NOT_VERIFIED',
  'CREDENTIAL_ACCOUNT_NOT_FOUND',
  'FAILED_TO_CREATE_SESSION',
  'AUTH_FORBIDDEN',
]);

/** Copy an allow-listed provider code only. Any other code or message is dropped. */
export function allowListedSignInCode(value: unknown): string | null {
  return typeof value === 'string' && allowedCodes.has(value) ? value : null;
}

export function reasonForHttp(status: number, code: string | null): SignInReason {
  if (code === 'INVALID_PASSWORD') return 'wrong_password';
  if (code === 'USER_NOT_FOUND' || code === 'USER_EMAIL_NOT_FOUND') return 'unknown_email';
  if (code === 'INVALID_EMAIL') return 'invalid_email';
  if (code === 'INVALID_EMAIL_OR_PASSWORD' || code === 'INVALID_CREDENTIALS') return 'credentials';
  if (code === 'PASSWORD_TOO_SHORT' || code === 'PASSWORD_TOO_LONG') return 'validation';
  if (code === 'EMAIL_NOT_VERIFIED') return 'unverified_email';
  if (code === 'CREDENTIAL_ACCOUNT_NOT_FOUND') return 'social_only';
  if (code === 'AUTH_FORBIDDEN') return 'forbidden';
  if (code === 'FAILED_TO_CREATE_SESSION') return 'service';
  if (status === 401) return 'credentials';
  if (status === 400 || status === 422) return 'validation';
  if (status === 403) return 'forbidden';
  if (status === 429) return 'rate_limited';
  return 'service';
}

const callbackMessages = new Set([
  'OIDC callback rejected',
  'OIDC transaction missing',
  'OIDC state mismatch',
  'Invalid return state',
]);
const networkMessages = new Set([
  'Failed to fetch',
  'Load failed',
  'NetworkError when attempting to fetch resource.',
  'Network request failed',
  'OIDC keys unavailable',
  'OIDC token exchange failed',
]);

function neonFailure(error: unknown): {status: number; code: string | null} | null {
  if (!(error instanceof Error) || error.message !== 'Neon session unavailable') return null;
  const status = (error as {status?: unknown}).status;
  const code = (error as {code?: unknown}).code;
  if (typeof status !== 'number') return null;
  return {status, code: typeof code === 'string' ? code : null};
}

export function describeSignInFailure(error: unknown): SignInReason {
  const http = neonFailure(error);
  if (http) return reasonForHttp(http.status, http.code);
  if (error instanceof TypeError) return 'network';
  if (error instanceof Error) {
    if (error.message === 'Invalid Google redirect') return 'google_redirect';
    if (error.message === 'Email and password required') return 'validation';
    if (error.message === 'Start sign-in again' || error.message === 'Invalid return transaction') return 'stale_transaction';
    if (networkMessages.has(error.message)) return 'network';
    if (callbackMessages.has(error.message)) return 'callback';
  }
  return 'session';
}

export const signInFailureCopy: Record<SignInReason, {en: string; 'zh-HK': string}> = {
  credentials: {
    en: 'Sign-in failed. That email and password do not match. The email may be unknown, or the password may be wrong. Check the email spelling, re-enter the password, or use Google if this account was created with Google.',
    'zh-HK': '登入失敗。此電郵與密碼不相符。可能是尚未有此電郵的帳戶，或密碼不正確。請核對電郵拼寫、重新輸入密碼，或若此帳戶以 Google 建立，請改用 Google 登入。',
  },
  wrong_password: {
    en: 'Sign-in failed. That password does not match this email. Re-enter the password, or use Google if this account was created with Google.',
    'zh-HK': '登入失敗。此密碼與此電郵不相符。請重新輸入密碼；若此帳戶以 Google 建立，請改用 Google 登入。',
  },
  unknown_email: {
    en: 'Sign-in failed. No BuyerOS account uses that email. Check the spelling, or ask an administrator to invite this address.',
    'zh-HK': '登入失敗。沒有使用此電郵的 BuyerOS 帳戶。請檢查拼寫，或請管理員邀請此電郵。',
  },
  invalid_email: {
    en: 'Sign-in failed. That email is not a complete address. Use the form name@company.com and try again.',
    'zh-HK': '登入失敗。此電郵不是完整地址。請使用 name@company.com 的格式再試一次。',
  },
  validation: {
    en: 'Sign-in failed. Enter the work email on your invitation and the password for that account, then try again.',
    'zh-HK': '登入失敗。請輸入邀請上的工作電郵及其密碼，然後再試一次。',
  },
  network: {
    en: 'Sign-in failed. The sign-in request did not reach the service. Check your connection and try again.',
    'zh-HK': '登入失敗。登入請求未能送達服務。請檢查連線後再試一次。',
  },
  rate_limited: {
    en: 'Sign-in failed. Too many attempts. Wait a moment, then try the same email and password again.',
    'zh-HK': '登入失敗。嘗試次數過多。請稍候，然後以同一電郵及密碼再試一次。',
  },
  service: {
    en: 'Sign-in failed. The sign-in service did not complete. Wait a moment and try again. Your password was cleared and the email above was kept.',
    'zh-HK': '登入失敗。登入服務未能完成。請稍候再試。密碼已清除，上方電郵仍保留。',
  },
  google_redirect: {
    en: 'Sign-in failed. Google did not return a trusted sign-in address. Choose Start again, then try Google once more.',
    'zh-HK': '登入失敗。Google 沒有返回可信任的登入地址。請選擇重新開始，然後再試一次 Google 登入。',
  },
  stale_transaction: {
    en: 'Sign-in failed. This page is no longer linked to your workspace. Choose Start again, then Sign in, and enter your email and password.',
    'zh-HK': '登入失敗。此頁已不再連接到你的工作區。請選擇重新開始，然後按登入，並輸入電郵及密碼。',
  },
  forbidden: {
    en: 'Sign-in failed. This site refused the sign-in request. Choose Start again and sign in from this BuyerOS page.',
    'zh-HK': '登入失敗。此網站拒絕了登入請求。請選擇重新開始，並在此 BuyerOS 頁面登入。',
  },
  unverified_email: {
    en: 'Sign-in failed. This email is not verified yet. Open the verification message, then sign in with the same email and password.',
    'zh-HK': '登入失敗。此電郵尚未完成驗證。請開啟驗證訊息，然後以同一電郵及密碼登入。',
  },
  social_only: {
    en: 'Sign-in failed. This email has no password on BuyerOS. Use Sign in with Google for this account.',
    'zh-HK': '登入失敗。此電郵在 BuyerOS 沒有密碼。請使用 Google 登入此帳戶。',
  },
  callback: {
    en: 'Sign-in failed. Please start again. The return link did not match this browser, so no workspace was opened. Use Sign in on this site and try again.',
    'zh-HK': '登入失敗，請重新開始。返回連結與此瀏覽器不相符，因此沒有開啟工作區。請在此網站按登入並再試一次。',
  },
  session: {
    en: 'Sign-in failed. Please start again. No workspace session was created. Use Sign in on this site and enter your email and password again.',
    'zh-HK': '登入失敗，請重新開始。沒有建立工作區登入階段。請在此網站按登入，並輸入電郵及密碼。',
  },
};

export function signInFailureMessage(reason: SignInReason, locale: 'en' | 'zh-HK'): string {
  const row = signInFailureCopy[reason];
  return locale === 'zh-HK' ? row['zh-HK'] : row.en;
}
