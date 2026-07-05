const ACCESS_TOKEN_KEY = "adr-flow.access_token";

function canUseSessionStorage(): boolean {
  return typeof window !== "undefined" && import.meta.client !== false;
}

export function getAccessToken(): string | null {
  if (!canUseSessionStorage()) {
    return null;
  }
  return sessionStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  if (!canUseSessionStorage()) {
    return;
  }
  sessionStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  if (!canUseSessionStorage()) {
    return;
  }
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
}
