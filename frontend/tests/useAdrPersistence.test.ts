import { effectScope, ref } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAdrPersistence } from "../app/composables/useAdrPersistence";

const getAccessTokenMock = vi.fn();

vi.mock("../composables/useApi", () => ({
  apiPath: (segment: string) => `/api${segment}`,
}));

vi.mock("../composables/useAuthToken", () => ({
  getAccessToken: () => getAccessTokenMock(),
}));

const fetchMock = vi.fn().mockResolvedValue(undefined);
vi.stubGlobal("fetch", fetchMock);

function createStore(overrides?: {
  isDirty?: boolean;
  status?: string;
  title?: string;
  content?: string;
}) {
  const isDirty = overrides?.isDirty ?? true;
  const currentAdr =
    overrides?.isDirty === false && !overrides?.title
      ? null
      : {
          id: "adr-1",
          title: overrides?.title ?? "Draft title",
          content: overrides?.content ?? "Draft content",
          status: overrides?.status ?? "draft",
        };

  return { currentAdr, isDirty };
}

describe("useAdrPersistence unload save", () => {
  let scope: ReturnType<typeof effectScope>;

  beforeEach(() => {
    fetchMock.mockClear();
    getAccessTokenMock.mockReset();
    scope = effectScope();
  });

  afterEach(() => {
    scope.stop();
  });

  function mountPersistence(
    store: ReturnType<typeof createStore>,
    adrId = ref("adr-1"),
  ) {
    scope.run(() => {
      useAdrPersistence(adrId, store as never);
    });
  }

  it("sends keepalive fetch with Bearer token on pagehide when dirty", () => {
    getAccessTokenMock.mockReturnValue("unload-token");
    const store = createStore();

    mountPersistence(store);
    window.dispatchEvent(new Event("pagehide"));

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/adrs/adr-1/save");
    expect(options.method).toBe("POST");
    expect(options.keepalive).toBe(true);
    expect(options.credentials).toBeUndefined();
    expect(options.headers).toEqual({
      Authorization: "Bearer unload-token",
      "Content-Type": "application/json",
    });
    expect(options.body).toBeInstanceOf(Blob);
  });

  it("skips unload save when no access token is stored", () => {
    getAccessTokenMock.mockReturnValue(null);
    const store = createStore();

    mountPersistence(store);
    window.dispatchEvent(new Event("pagehide"));

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("skips unload save when the draft is clean", () => {
    getAccessTokenMock.mockReturnValue("unload-token");
    const store = createStore({ isDirty: false });

    mountPersistence(store);
    window.dispatchEvent(new Event("pagehide"));

    expect(fetchMock).not.toHaveBeenCalled();
  });
});
