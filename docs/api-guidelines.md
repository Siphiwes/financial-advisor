# API guidelines

- Keep HTTP routing thin. Put business rules in service functions.
- Validate incoming data with explicit request schemas and return stable response schemas.
- Use consistent HTTP status codes and structured error responses.
- Version public business endpoints under `/api/v1` when they are introduced. Keep system endpoints such as `/health` separate.
- Add pagination and bounded query parameters to list endpoints.
- Make import and create operations idempotent where retries could otherwise create duplicate financial records.
- Never expose internal exceptions, credentials or stack traces to API clients.
- Add tests for success, validation failures, authorization boundaries and provider failures.
