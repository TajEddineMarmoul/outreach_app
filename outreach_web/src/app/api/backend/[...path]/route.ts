import { auth } from "@clerk/nextjs/server";
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const maxDuration = 300;

async function proxyRequest(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
): Promise<Response> {
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  }

  const apiToken = process.env.APP_ACCESS_TOKEN || "";
  const backendUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "";
  if (!apiToken || !backendUrl) {
    return NextResponse.json({ detail: "Backend connection is not configured" }, { status: 503 });
  }

  const { path } = await context.params;
  const target = new URL(path.join("/"), `${backendUrl.replace(/\/$/, "")}/`);
  target.search = request.nextUrl.search;

  const headers = new Headers(request.headers);
  headers.delete("authorization");
  headers.delete("cookie");
  headers.delete("host");
  headers.delete("content-length");
  headers.set("authorization", `Bearer ${apiToken}`);

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  const backendResponse = await fetch(target, {
    method: request.method,
    headers,
    body: hasBody ? await request.arrayBuffer() : undefined,
    redirect: "manual",
    cache: "no-store",
  });

  const responseHeaders = new Headers();
  for (const name of ["content-type", "content-disposition", "cache-control", "location"]) {
    const value = backendResponse.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }

  return new Response(backendResponse.body, {
    status: backendResponse.status,
    headers: responseHeaders,
  });
}

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const PATCH = proxyRequest;
export const DELETE = proxyRequest;
