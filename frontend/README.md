# Odin Advisor Frontend

React + TypeScript + Vite frontend for Odin Study Skill Advisor.

## Current Features

- authenticated advisor workspace
- persistent conversation list
- conversation search
- rename/delete
- temporary chat
- response copy/export
- daily usage display
- dark/light themes
- multi-persona new-chat advisor selector
- active-conversation advisor badge

## Persona UX

The frontend loads:

```http
GET /personas
```

and renders enabled advisor choices.

The selector applies only to new persistent conversations.

Example:

```text
Advisor for next chat
[ Hela ▼ ]
```

Creating a new conversation sends:

```json
{
  "title": "New Conversation",
  "persona_id": "persona_2"
}
```

The active chat header reads the persona stored on the conversation.

Changing the selector does not change an existing chat.

## Development

```powershell
npm install
npm run dev
```

Default Vite URL:

```text
http://localhost:5173
```

The backend should normally run at:

```text
http://127.0.0.1:8000
```

## Validation

```powershell
npm run lint
npm run build
```

Rerun these after UI changes before handoff.

## Responsive Layout

The advisor sidebar is designed so that:

- branding stays visible
- new-chat persona picker stays visible
- settings and temporary chat stay visible
- usage information stays visible
- logout stays visible
- the conversation list consumes remaining height and scrolls

This avoids requiring users to zoom out to access the persona picker on typical laptop displays.
