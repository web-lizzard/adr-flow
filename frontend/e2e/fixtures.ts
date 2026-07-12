import { readFile } from "node:fs/promises";

import { test as base, expect } from "@playwright/test";

const authFile = ".auth/user.json";

type StorageEntry = { name: string; value: string };

type AuthStorageState = {
  origins?: Array<{
    sessionStorage?: StorageEntry[];
  }>;
};

export { expect };

export const test = base.extend({
  context: async ({ context }, use, testInfo) => {
    if (testInfo.project.name !== "setup") {
      const storageState = JSON.parse(
        await readFile(authFile, "utf8"),
      ) as AuthStorageState;
      const sessionStorage =
        storageState.origins?.flatMap(
          (origin) => origin.sessionStorage ?? [],
        ) ?? [];

      if (sessionStorage.length > 0) {
        await context.addInitScript((items: StorageEntry[]) => {
          for (const { name, value } of items) {
            sessionStorage.setItem(name, value);
          }
        }, sessionStorage);
      }
    }

    await use(context);
  },
});
