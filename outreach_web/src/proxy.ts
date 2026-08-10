import { NextRequest, NextResponse } from "next/server";

const SESSION_COOKIE = "outreach_session";

export default function proxy(request: NextRequest) {
  const expected = process.env.APP_SESSION_TOKEN;
  const received = request.cookies.get(SESSION_COOKIE)?.value;
  const authenticated = Boolean(expected && received === expected);
  const { pathname } = request.nextUrl;

  if (pathname.startsWith("/api/auth")) return NextResponse.next();

  if (pathname.startsWith("/sign-in") || pathname.startsWith("/sign-up")) {
    if (authenticated) return NextResponse.redirect(new URL("/campaigns", request.url));
    return NextResponse.next();
  }

  if (!authenticated) {
    if (pathname.startsWith("/api/")) {
      return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
    }
    const signInUrl = new URL("/sign-in", request.url);
    signInUrl.searchParams.set("next", `${pathname}${request.nextUrl.search}`);
    return NextResponse.redirect(signInUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
