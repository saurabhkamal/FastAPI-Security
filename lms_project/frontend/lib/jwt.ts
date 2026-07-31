interface JwtPayload {
  sub: string;
  email: string;
  role: string;
  exp: number;
}

// Decodes (does NOT verify) a JWT payload client-side, purely to read display
// fields like sub/email/role. The server independently verifies the signature
// on every request - this is never used for trust decisions.
export function decodeJwt(token: string): JwtPayload | null {
  try {
    const [, payload] = token.split(".");
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const json = decodeURIComponent(
      atob(normalized)
        .split("")
        .map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"))
        .join("")
    );
    return JSON.parse(json) as JwtPayload;
  } catch {
    return null;
  }
}
