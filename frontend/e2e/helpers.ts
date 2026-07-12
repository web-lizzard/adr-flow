import { readFile } from "node:fs/promises";

import type { APIRequestContext } from "@playwright/test";

const authFile = ".auth/user.json";
const ACCESS_TOKEN_KEY = "adr-flow.access_token";

type AuthStorageState = {
  origins?: Array<{
    sessionStorage?: Array<{ name: string; value: string }>;
  }>;
};

export const COMPLETE_ADR_CONTENT = `## Context

We need to choose a database for the project.

## Options

1. PostgreSQL
2. MongoDB

## Decision

We will use PostgreSQL.

## Status

Accepted

## Consequences

Positive: ACID compliance. Negative: operational overhead.
`;

export async function getAuthToken(): Promise<string> {
  const storageState = JSON.parse(
    await readFile(authFile, "utf8"),
  ) as AuthStorageState;

  const sessionStorage =
    storageState.origins?.flatMap((origin) => origin.sessionStorage ?? []) ??
    [];

  const token = sessionStorage.find(
    (entry) => entry.name === ACCESS_TOKEN_KEY,
  )?.value;

  if (!token) {
    throw new Error(`Missing ${ACCESS_TOKEN_KEY} in ${authFile}`);
  }

  return token;
}

export async function createAdr(
  request: APIRequestContext,
  title: string,
): Promise<{ id: string }> {
  const token = await getAuthToken();
  const response = await request.post("/api/adrs", {
    headers: { Authorization: `Bearer ${token}` },
    data: { title },
  });

  if (!response.ok()) {
    throw new Error(
      `createAdr failed: ${response.status()} ${await response.text()}`,
    );
  }

  return (await response.json()) as { id: string };
}

export async function seedAdrContent(
  request: APIRequestContext,
  id: string,
  content: string,
): Promise<void> {
  const token = await getAuthToken();
  const response = await request.patch(`/api/adrs/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { content },
  });

  if (!response.ok()) {
    throw new Error(
      `seedAdrContent failed: ${response.status()} ${await response.text()}`,
    );
  }
}

export function uniqueTitle(prefix: string): string {
  return `${prefix} ${Date.now()}`;
}
