# Legacy GCP deployment secrets

The production application now deploys through the connected Vercel projects.
This GitHub workflow is manual-only and remains available solely as a legacy
fallback; it is not part of the free production path.

Add these repository secrets before using `.github/workflows/deploy-gcp.yml`:

- `GCP_WORKLOAD_IDENTITY_PROVIDER`: `projects/166059707324/locations/global/workloadIdentityPools/github-pool/providers/github-provider`
- `GCP_SERVICE_ACCOUNT`: `github-deployer@mailsender-501713.iam.gserviceaccount.com`
- `BACKEND_URL`: `https://outreach-backend-bnjd5uovna-uc.a.run.app`
- `APP_ACCESS_TOKEN`: shared private token for the frontend proxy and API.
- `APP_USER_ID`: database owner ID returned for the private API token.
- `APP_SESSION_TOKEN`: private frontend session-cookie value.
- `APP_LOGIN_PASSWORD`: private workspace password.
- `WORKER_TICK_TOKEN`: the same random token configured on the API and Scheduler.

The workflow never reads `.env` or `.env.local` from the repository.
