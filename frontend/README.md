# Odin frontend

React 19, TypeScript, Vite 8, Tailwind 4, React Router, Axios and react-markdown. Use Node.js 24 and npm. Full setup is in [the root README](../README.md).

From this directory:

1. Run `npm ci`.
2. Copy `.env.example` to `.env.local`; set `VITE_API_URL=http://localhost:8000`.
3. Start the backend using the root instructions, then run `npm run dev`.
4. Open `http://localhost:5173`.

`npm run lint` checks ESLint. `npm run build` runs TypeScript and builds to `dist/`. `npm run preview` serves that bundle locally. Set `VITE_API_URL` before deployment builds; all `VITE_` variables are public.

`src/App.tsx` contains chat; `src/pages/` contains Login, Settings and Admin. Shared navigation/dialogs are in `src/components/`; `src/api/client.ts` configures cookie-authenticated requests. Fonts/icons are in `public/`, imagery in `src/assets/`. SPA deployment routing is in `vercel.json`.

Lint/build are not browser or deployment integration tests. See [verification](../docs/FINAL_VERIFICATION.md).
