# CI/CD

Two GitHub Actions workflows live in `.github/workflows/`.

## CI (`ci.yml`): every pull request and every push to `main`

| Job | What it does |
|---|---|
| Backend tests | Installs `api/requirements-dev.txt` and runs `pytest tests`. No LLM calls are made, and tests that need the (private) dataset skip themselves. |
| Flutter analyze + test | `flutter analyze` and `flutter test` in `app/`. |

No setup is needed; it works as soon as the workflow is on `main`. Turn on branch protection
(Settings → Branches → `main` → "Require status checks to pass") so PRs cannot merge while CI is red.

## CD (`deploy.yml`): every push to `main` (for example, a merged PR), or run manually

| Job | What it does |
|---|---|
| Build Android APK | Runs the app tests and builds the release APK. Download it from the workflow run's **Artifacts** section (kept 30 days). |
| Deploy API to EC2 | Runs the backend tests, then redeploys the existing server with `deploy/aws_deploy.sh` and smoke-tests `/health`. **Skipped until it is enabled (below).** |

### Enabling the deploy job (repository owner, once)

Settings → Secrets and variables → Actions.

**Secrets**

| Name | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Keys of an IAM user that has the `deploy/iam-policy.json` permissions. Use a dedicated deploy user, not a personal one. |
| `EC2_SSH_KEY` | Full contents of `hemosense-key.pem` (the instance's SSH private key). |
| `HEMOSENSE_ENV` | Full contents of the production `api/.env` (OpenRouter key, model lists, etc.). |

**Variables**

| Name | Value |
|---|---|
| `DEPLOY_ENABLED` | `true` |
| `EC2_INSTANCE_ID`, `EC2_SG_ID`, `EC2_ALLOC_ID`, `EC2_IP` | The `INSTANCE_ID`, `SG`, `ALLOC` and `IP` values from `deploy/.aws_state` on the machine that first provisioned the server. |

How the deploy job stays safe:
- It opens SSH (port 22) only for the runner's own IP and closes it again, even when the job fails.
- It deletes the key and `.env` from the runner at the end.
- It runs in the `production` environment, so you can require a manual approval (Settings → Environments → production → Required reviewers).

### Notes
- The RAG index (`models/rag_index.json`) is not in git. When a deploy bundle has none, the server keeps
  the index it already has. To change it, rebuild locally (`python -m hemosense.rag build research/rag_sources models/rag_index.json`)
  and run `bash deploy/aws_deploy.sh` from that machine.
- The server reaches Bedrock through its EC2 instance role, so no AWS keys are stored on it.
