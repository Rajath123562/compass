# Web app checklist
- Decide: SPA vs server-rendered; frontend framework, backend, database, auth. Pin versions.
- Structure: separate UI, API/data layer, config. No business logic in UI components.
- Auth: hashed passwords (bcrypt/argon2), secure session or JWT handling, logout, protected routes, per-user data checks.
- Forms: client AND server validation; show field errors; prevent double submit.
- States: loading, empty, error, success for every data view.
- Data: migrations, indexes on queried fields, pagination for lists.
- Routing: 404 page, redirect unauthenticated users, deep links work on refresh.
- SEO/meta where public: title, description, social tags.
- Test: unit for logic, integration for API, one end-to-end for the main journey.
