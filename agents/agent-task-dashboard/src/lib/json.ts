export function parseJson<T>(value: string | null | undefined, fallback: T): T {
  if (!value) return fallback;
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

export function stringifyJson(value: unknown) {
  return JSON.stringify(value ?? null, null, 2);
}

export function linesToJsonArray(value: string | null | undefined) {
  return JSON.stringify(
    (value ?? "")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean),
    null,
    2,
  );
}
