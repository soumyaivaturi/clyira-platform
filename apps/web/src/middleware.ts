import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_AUTH_PREFIXES = ["/auth/login", "/auth/register", "/auth/forgot", "/auth/onboarding"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // "/" must be exact-matched — using startsWith("/") would match every path
  const isPublic = pathname === "/" || PUBLIC_AUTH_PREFIXES.some((p) => pathname.startsWith(p));
  const token = request.cookies.get("clyira_token")?.value;

  // Unauthenticated → redirect to login (for protected routes)
  if (!isPublic && !token) {
    const url = request.nextUrl.clone();
    url.pathname = "/auth/login";
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  // Already authenticated → skip login/register (but allow onboarding)
  if (isPublic && token && pathname !== "/auth/forgot" && pathname !== "/auth/onboarding") {
    const url = request.nextUrl.clone();
    url.pathname = "/dashboard";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api).*)"],
};
