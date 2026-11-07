# CanineSense API

Base path: `/api`. Authenticated routes require `Authorization: Bearer <token>`.

Identity is taken only from the JWT. `X-User-Id` is ignored.

## Auth

- `POST /auth/register` `{email, password, name}`
- `POST /auth/login` `{email, password}`
- `POST /auth/logout`
- `GET /auth/me`
- `POST /auth/change-password` `{current_password, new_password}`

## Dogs

- `GET /dogs`
- `POST /dogs`
- `GET /dogs/{id}`
- `PATCH /dogs/{id}`
- `DELETE /dogs/{id}`

## Recordings / Engine A

- `POST /recordings/analyze` multipart `file`, optional `dog_id`, `source`
- `GET /recordings`
- `GET /recordings/{id}`
- `DELETE /recordings/{id}`
- `GET /recordings/{id}/media/{original|processed|spectrogram|waveform}`

## Engine B

- `POST /communicate/intent` `{text}`
- `POST /communicate/generate` `{text, dog_id?, intent_override?}`
- `GET /communicate`
- `GET /communicate/{id}/audio`
- `POST /communicate/{id}/response` multipart `file`

## Account

- `GET /analytics/summary`
- `GET /account/export`
- `DELETE /account`
- `GET /models/current`
- `GET /health`
