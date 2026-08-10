import { timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const SESSION_COOKIE = "outreach_session";

function equalSecret(received: string, expected: string): boolean {
  const receivedBuffer = Buffer.from(received);
  const expectedBuffer = Buffer.from(expected);
  return receivedBuffer.length === expectedBuffer.length && timingSafeEqual(receivedBuffer, expectedBuffer);
}

async function authenticated(): Promise<boolean> {
  const sessionToken = process.env.APP_SESSION_TOKEN || "";
  const received = (await cookies()).get(SESSION_COOKIE)?.value || "";
  return Boolean(sessionToken && received && equalSecret(received, sessionToken));
}

export async function GET() {
  const isAuthenticated = await authenticated();
  return NextResponse.json({
    authenticated: isAuthenticated,
    ...(isAuthenticated
      ? {
          user: {
            fullName: process.env.APP_DISPLAY_NAME || "Taj Eddine Marmoul",
            email: process.env.APP_EMAIL || "tajdinetajdine1@gmail.com",
            publicMetadata: { role: "admin" },
          },
        }
      : {}),
  });
}

export async function POST(request: NextRequest) {
  const configuredPassword = process.env.APP_LOGIN_PASSWORD || "";
  const sessionToken = process.env.APP_SESSION_TOKEN || "";
  if (!configuredPassword || !sessionToken) {
    return NextResponse.json({ detail: "Sign-in is not configured" }, { status: 503 });
  }

  const body = (await request.json().catch(() => ({}))) as { password?: string };
  if (!body.password || !equalSecret(body.password, configuredPassword)) {
    return NextResponse.json({ detail: "The password is incorrect" }, { status: 401 });
  }

  const response = NextResponse.json({ authenticated: true });
  response.cookies.set(SESSION_COOKIE, sessionToken, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });
  return response;
}

export async function DELETE() {
  const response = NextResponse.json({ authenticated: false });
  response.cookies.set(SESSION_COOKIE, "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
  return response;
}
