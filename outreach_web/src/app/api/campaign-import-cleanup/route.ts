import { auth } from "@clerk/nextjs/server";
import { del } from "@vercel/blob";
import { NextResponse } from "next/server";

const PRIVATE_IMPORT_HOST_SUFFIX = ".private.blob.vercel-storage.com";
const PRIVATE_IMPORT_PATH_PREFIX = "/campaign-imports/";

function isPrivateImportUrl(value: unknown): value is string {
  if (typeof value !== "string") return false;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && url.hostname.endsWith(PRIVATE_IMPORT_HOST_SUFFIX) && url.pathname.startsWith(PRIVATE_IMPORT_PATH_PREFIX) && !url.search && !url.hash;
  } catch {
    return false;
  }
}

export async function POST(request: Request): Promise<NextResponse> {
  const { userId } = await auth();
  if (!userId) return NextResponse.json({ detail: "Authentication required" }, { status: 401 });

  const body = await request.json().catch(() => null) as { urls?: unknown } | null;
  const urls = Array.isArray(body?.urls) ? body.urls.filter(isPrivateImportUrl) : [];
  if (!urls.length || urls.length > 20) return NextResponse.json({ detail: "No valid import files were supplied" }, { status: 422 });

  await del(urls);
  return new NextResponse(null, { status: 204 });
}
