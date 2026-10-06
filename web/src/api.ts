export type Data = Record<string, any>;
export async function api<T = Data>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch("/api" + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (!response.ok) {
    const body = await response
      .json()
      .catch(() => ({ detail: "The studio could not be reached." }));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : body.detail?.map((x: Data) => x.msg).join("; ") || "Request failed",
    );
  }
  return response.json();
}
export const send = <T = Data>(path: string, body: unknown, method = "POST") =>
  api<T>(path, { method, body: JSON.stringify(body) });
export const artifact = (project: string, file: string) =>
  `/api/artifacts/${project}/${encodeURIComponent(file)}`;
