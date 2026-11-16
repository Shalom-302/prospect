import type { NextRequest } from "next/server";
import { proxy } from "@/lib/server/proxy";

export const dynamic = "force-dynamic";
// Génération de lettres / lots : laisser le temps au LLM.
export const maxDuration = 300;

type Ctx = { params: Promise<{ path: string[] }> };
const handler = async (req: NextRequest, ctx: Ctx) => proxy(req, (await ctx.params).path);

export { handler as GET, handler as POST, handler as PUT, handler as PATCH, handler as DELETE };
