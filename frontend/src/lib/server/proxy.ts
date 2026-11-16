// Côté serveur uniquement : relaie les appels same-origin /api/* du navigateur vers FastAPI
// (même BFF que Foody / SignalLab). L'URL de l'API est lue à l'exécution (API_INTERNAL_URL) :
// une seule image GHCR pour n'importe quel domaine Dokploy. Le cookie de session reste first-party.
import type { NextRequest } from "next/server";

const API_URL = (process.env.API_INTERNAL_URL || "http://127.0.0.1:8010").replace(/\/$/, "");
const FORWARD_REQUEST = ["content-type", "cookie", "accept", "accept-language", "user-agent"];
const FORWARD_RESPONSE = ["content-type", "content-disposition", "cache-control", "location"];

function clientIp(req: NextRequest): string {
  // Dernière entrée = celle ajoutée par Traefik (Dokploy) ; la première est forgeable.
  const fwd = req.headers.get("x-forwarded-for");
  if (fwd) return fwd.split(",").at(-1)!.trim();
  return req.headers.get("x-real-ip") || "0.0.0.0";
}

export async function proxy(req: NextRequest, parts: string[]): Promise<Response> {
  if (parts.some((p) => p === "." || p === ".." || p === "")) {
    return Response.json({ detail: "Route non disponible" }, { status: 404 });
  }
  const path = parts.map(encodeURIComponent).join("/");
  const headers = new Headers();
  for (const name of FORWARD_REQUEST) {
    const v = req.headers.get(name);
    if (v) headers.set(name, v);
  }
  headers.set("x-forwarded-for", clientIp(req));
  headers.set("x-forwarded-proto", req.nextUrl.protocol.replace(":", ""));
  const hasBody = !["GET", "HEAD"].includes(req.method);
  let upstream: Response;
  try {
    upstream = await fetch(`${API_URL}/api/${path}${req.nextUrl.search}`, {
      method: req.method,
      headers,
      body: hasBody ? await req.arrayBuffer() : undefined,
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    return Response.json({ detail: "API injoignable" }, { status: 502 });
  }
  const out = new Headers();
  for (const name of FORWARD_RESPONSE) {
    const v = upstream.headers.get(name);
    if (v) out.set(name, v);
  }
  for (const cookie of upstream.headers.getSetCookie()) out.append("set-cookie", cookie);
  return new Response(upstream.body, { status: upstream.status, headers: out });
}
