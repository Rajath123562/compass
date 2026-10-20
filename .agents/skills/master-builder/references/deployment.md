# Deployment checklist
- Confirm host and plan fit the stack and my budget (free tiers have limits: sleep, storage, bandwidth).
- Production config separate from development; all env variables set on the host, none committed.
- Run a production build locally first and fix warnings.
- Database: production instance, migrations run, backup enabled.
- Domain, HTTPS, CORS origins, and callback URLs updated for production.
- Health check URL, error monitoring, and logs available.
- Smoke test after deploy: open the app, run the main journey, check logs for errors.
- Rollback plan: how to redeploy the previous version; tag releases in Git.
- Provide numbered step-by-step instructions for my specific host.
