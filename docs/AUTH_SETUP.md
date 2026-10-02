# Authentication and dashboard rollout

> Submission note (October 2, 2026): deployment/branch status below is historical.
> See `FINAL_VERIFICATION.md` for the current local/remote comparison. The current
> `backend/auth_security.py` implements SMTP email delivery; Resend configuration
> notes below do not establish that an HTTPS transport is implemented. Google
> OAuth sign-in/linking is included as a feedback-driven feature in `../PRD.md`.

## Deployment status

The source changes are local and have not been committed, pushed, or deployed.
The Google OAuth variables and production FRONTEND_URL have been saved to the
primary Render service with owner authorization. That environment update completed
a successful redeploy of existing commit `5c30f78` (Render deploy
`dep-davat71srm7s73b9lq90`, status `live`); it does not include the local OAuth routes.
The connected Render `Advisor-Console` service serves
`https://advisor-console.onrender.com` from `RedGla/Odin-Study-Skill-Advisor`,
branch `dev`, directory `backend`. This checkout's remote is
`RedGla/Eskwelabs-Advisor-Console`. Verify the repository relationship before
publishing. A second Render service, `Advisor-Console-1`, uses another branch
and root directory; do not deploy to it by accident.

The connected Supabase database reported Alembic revision `ef56ab67bc90`.
Its missing migration was recovered unchanged from repository commit `6e190af`
and matched against GitHub blob `4c128d2cc056fe0a15d68d06bb0330522d965028`.
The new auth migration `ef56ab78cd90` follows it. No live database changes were
made. Do not stamp over the live revision.

Local `dev` was at `227a98d`, while `origin/dev` includes newer workspace UI
changes through `5c30f78`. Integrate this work with that branch before publishing;
do not overwrite those newer features with the older checkout. The Vercel
connector returned no teams. The frontend origin supplied by the owner is
`https://advisor-console-nine.vercel.app`; Vercel environment settings could not
be inspected through the connector.

## Google sign-in

1. In Google Cloud, configure the OAuth consent screen and a **Web application**
   OAuth client. Request only `openid email profile`. Add test users while the
   app is in testing mode, and publish the consent screen for general access.
2. Register the exact authorized redirect URI:
   `https://advisor-console.onrender.com/auth/google/callback` for the primary
   Render service above. For local development, register
   `http://localhost:8000/auth/google/callback` on a development client.
3. Configure backend environment variables:
   - `GOOGLE_OAUTH_CLIENT_ID`
   - `GOOGLE_OAUTH_CLIENT_SECRET`
   - `GOOGLE_OAUTH_REDIRECT_URI` (the exact URI registered in Google Cloud)
4. Set `FRONTEND_URL=https://advisor-console-nine.vercel.app` (without `/login`).
   On Vercel, set `VITE_API_URL=https://advisor-console.onrender.com` and rebuild.
   The repository production environment files now contain these public URLs.
   OAuth secrets belong only on the backend, never in a `VITE_` variable.

For `Error 400: redirect_uri_mismatch`, open Google Cloud's Google Auth Platform
**Clients** page and select the Web application client whose client ID matches
Render's `GOOGLE_OAUTH_CLIENT_ID`. Under **Authorized redirect URIs**, add exactly
`https://advisor-console.onrender.com/auth/google/callback` and save. Do not add
`flowName=GeneralOAuthFlow`, a trailing slash, or the frontend URL. Adding this
only under **Authorized JavaScript origins** does not register the callback.
Start a fresh sign-in after saving. This Google-side registration cannot be
fixed by removing the application's email-verification requirement.

Local OAuth credentials are stored in Git-ignored `backend/.env` with the
localhost callback. Shared templates intentionally contain no client secret.
Saving local files does not configure Render or register callbacks in Google Cloud.

The existing Google Docs service account is **not** an OAuth client. The login
button remains disabled until the OAuth environment variables are present.
The dashboard reports configuration presence; this does not prove credentials
are valid. Test a real consent flow after deployment.

Google identities use their verified provider subject. Matching email alone
never links an existing account. Existing users sign in with their password
and select **Link Google account** in Settings. Use the same verified email.
New Google users receive a normal user role; Google claims cannot grant admin.
Google-only users may use password recovery to set a password.

## Verification and password recovery email

### Resend (recommended on Render Free)

Set `RESEND_API_KEY` in the backend deployment environment. Odin calls Resend's
HTTPS API with the existing HTTP client; no extra SDK is required. When this key
is configured, Resend takes precedence over SMTP. Set `RESEND_FROM` to your
verified sender, or use `Odin <onboarding@resend.dev>` for testing.

**Without a domain, this test sender sends only to the email address associated
with your Resend account.** Sign up with the inbox you want to test. Other users'
verification and password-reset messages require a verified sending domain.
See [Resend test-recipient restrictions](https://resend.com/docs/knowledge-base/403-error-resend-dev-domain).
The `resend.dev` address is a sender; it is not the recipient's address.

Create a sending API key in Resend, save it directly in Render's environment
settings, and redeploy the backend with this code. Keep the key out of Git and
frontend `VITE_` variables. `FRONTEND_URL` must be the real frontend origin so
links open the correct login page. After deployment, test **Forgot password?**
for your existing Odin account using the same inbox as your Resend account.
Local mocked tests verify integration and failure handling, not inbox delivery.

[Render Free blocks outbound SMTP ports 25, 465 and 587](https://render.com/changelog/free-web-services-will-no-longer-allow-outbound-traffic-to-smtp-ports).
Use the HTTPS integration on that tier; adding SMTP credentials alone will not
provide delivery. Upgrade the sender to a verified domain before inviting others.

### SMTP (existing supported transport)

Choose an SMTP delivery provider, verify a sender/domain with that provider,
and configure its SPF/DKIM records. Set these backend variables:

```env
SMTP_HOST=your-provider-smtp-host
SMTP_PORT=587
SMTP_FROM=Odin <accounts@your-verified-domain>
SMTP_USERNAME=your-provider-username
SMTP_PASSWORD=your-provider-secret
```

Port 587 uses STARTTLS; port 465 uses implicit TLS. Certificate verification
is always enabled. SMTP credentials are optional only for a trusted relay that
does not require authentication. Provider delivery charges, if any, are separate
from AI token costs. No email service or paid resource has been provisioned.

Registration does not require email delivery or inbox verification. After signup,
users return to the sign-in form and can log in with their password immediately.
Password recovery still requires email delivery. Previously issued verification
links remain usable, but verifying an email is optional for login and chat.
Links expire in 30 minutes, are stored only as hashes, and are single-use.
Tokens appear in URL fragments and are removed from the page URL after loading.
Password reset revokes all sessions; a password change revokes other sessions
and rotates the current one. New passwords require 15–128 characters. Existing
passwords remain usable without email verification.

**Existing accounts are not marked verified.** Their email ownership metadata
is preserved, but existing users and admins can sign in without verification.
Ordinary users can use chat regardless of verification status. Google identity
validation, explicit account linking, suspension, role restrictions, and session
protections remain enforced. No data migration is needed for this policy change.

## Cookies, origins, and deployment

Production requires `ENVIRONMENT=production`, `COOKIE_SECURE=true`, and an
HTTPS `FRONTEND_URL`. Use `COOKIE_SAMESITE=none` for separate Vercel/Render sites.
Every browser mutation requires an allowed `Origin` (or matching `Referer`
when Origin is absent), including login, registration and Google flow start.
Backend sessions are opaque, hashed in the database, HttpOnly, and expire
after 12 hours. Raw user-ID cookies are never authentication, even locally.

Some browsers block third-party cookies entirely. Prefer frontend and backend
custom domains under the same site (for example `app.your-domain` and
`api.your-domain`) and `COOKIE_SAMESITE=lax`, or an explicitly configured
same-origin backend proxy. Do not disable cookie or CSRF protections to fix this.
Login checks that the cookie actually worked and displays a specific error.
Configure trusted proxy forwarding to obtain the real client address; do not
trust arbitrary forwarded headers from the public internet.

After integrating with the deployed branch, run `alembic upgrade head`
from `backend` using the deployed database credentials. The migration aborts
on duplicate case-insensitive emails instead of merging accounts. New auth
tables enable RLS and deny Supabase browser roles. Only the backend database
role should have access. Keep database credentials out of frontend code.

## Admin dashboard and temporary chats

Admins land on `/admin`. All normal and temporary chat API routes reject
admins, even if a URL is entered manually. The dashboard provides:

- Usage/spend totals, conversation inspection and operational events.
- Email search, verification/account status, suspension/reactivation and session
  revocation. Suspension invalidates sessions and outstanding account tokens.
- Immediate signup/chat pause controls and bounded numeric usage/rate limits.
- Database connectivity, active session count and Google/email setup status.
- Audit records for account and application-rule changes.

Administrator accounts cannot be suspended from the dashboard, preventing
accidental administrator lockout. Role assignment and database schema/RLS
changes remain privileged deployment operations. Prompt/grounding documents
still use the existing Google Docs integration. This is an application control
panel, not an arbitrary SQL console or replacement for infrastructure tools.

Temporary chat messages live only in component memory and request processing.
Leaving the chat, navigating away, logging out or refreshing discards them.
They never enter conversation/message tables or content-bearing telemetry.
Daily usage and content-free completion metadata are still recorded; normal
rate and token caps apply. Context is bounded to the latest 50 messages and
64,000 characters. Provider failures retain uncertain token reservations until
the daily reset, matching the existing conservative quota policy. The model
provider may retain requests under its own policy; temporary mode does not
promise provider-side deletion or zero retention.

Cross-chat AI memory was intentionally omitted. Reintroducing remembered facts
would consume prompt tokens, so no increase in token cost could not be guaranteed.
Existing conversation context is unchanged and no summarization/embedding
calls were added.

## Validation and remaining work

Local verification on 2026-10-02: **91 backend tests passed** on PostgreSQL
16.15 after exercising the new migration downgrade/upgrade. Frontend ESLint,
TypeScript and production build passed. Browser checks confirmed admin login
and direct-root navigation return to the dashboard, ordinary users can use
temporary chat, and refreshing discards temporary content. The local database
contained zero message rows and zero content-bearing telemetry after a temporary
turn, while its usage counter incremented. Browser console checks reported no
errors during those flows. Test report: `test-results/account-security.xml`.

Run `python -m pytest -q` against the disposable local PostgreSQL database
described in TESTING.md; run `npm run lint` and `npm run build` in `frontend`.
Tests mock email delivery, Google token verification, and LLM calls; they do not
verify live OAuth credentials, SMTP delivery or provider retention. After setup,
exercise registration, verify/resend, reset, Google consent/cancellation/linking,
admin redirect, user suspension, and temporary chat on the real domains.

This hardens the existing architecture; it is not a security certification.
MFA/passkeys, a breached-password corpus, durable email queues and full edge
bot protection are not implemented. Authentication throttles are shared through
PostgreSQL; the pre-existing chat rate limiter remains per-process. Daily
message/token limits remain database-backed. Keep infrastructure-level limits
and monitoring in place as the application scales.

References: [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect),
[OWASP authentication guidance](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html),
[Supabase API security](https://supabase.com/docs/guides/api/securing-your-api).
