# CSRF and session-origin protection

All state-changing requests (`POST`, `PUT`, `PATCH`, and `DELETE`), including login and registration without a session cookie, must include an `Origin` matching an entry in `ALLOWED_ORIGINS`. `ALLOWED_ORIGINS` contains `FRONTEND_URL`, plus supported local development URLs when `ENVIRONMENT=development`.

If a browser omits `Origin`, a well-formed `Referer` with an allowed origin is accepted as a fallback. When `Origin` is present, it is authoritative: a hostile origin is rejected even if an allowed `Referer` is also supplied. Missing, malformed, and hostile origins receive HTTP 403. Login and registration also require a valid origin to prevent login CSRF. Health checks and safe methods are not blocked.

`CORSMiddleware` wraps origin protection, so allowed browser origins receive CORS headers on both normal responses and CSRF rejections, while `OPTIONS` preflight remains a safe method and bypasses CSRF validation.

This explicit origin check is required because production may use `SameSite=None` for the cross-origin Vercel-to-backend deployment. The session token remains HttpOnly and is never exposed to JavaScript. `COOKIE_SECURE=true` is required in production.
