import { beforeEach, describe, expect, it } from "vitest";
import {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from "../composables/useAuthToken";

const TOKEN_KEY = "adr-flow.access_token";

describe("useAuthToken", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("stores and retrieves the access token in sessionStorage", () => {
    setAccessToken("jwt-token-123");

    expect(sessionStorage.getItem(TOKEN_KEY)).toBe("jwt-token-123");
    expect(getAccessToken()).toBe("jwt-token-123");
  });

  it("clears the access token from sessionStorage", () => {
    setAccessToken("jwt-token-123");

    clearAccessToken();

    expect(sessionStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(getAccessToken()).toBeNull();
  });
});
