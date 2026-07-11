# GitHub deployment secrets

Add these repository secrets before using `.github/workflows/deploy-gcp.yml`:

- `GCP_WORKLOAD_IDENTITY_PROVIDER`: `projects/166059707324/locations/global/workloadIdentityPools/github-pool/providers/github-provider`
- `GCP_SERVICE_ACCOUNT`: `github-deployer@mailsender-501713.iam.gserviceaccount.com`
- `BACKEND_URL`: `https://outreach-backend-bnjd5uovna-uc.a.run.app`
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`: Clerk publishable key.
- `CLERK_SECRET_KEY`: Clerk server secret.
- `WORKER_TICK_TOKEN`: the same random token configured on the API and Scheduler.

The workflow never reads `.env` or `.env.local` from the repository.
