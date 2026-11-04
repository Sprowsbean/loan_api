# Production Checklist: loan-api

Image: `sprows/loan-api:1.0.0` (also tagged `latest`)

## 1. Slim base image

```bash
grep FROM Dockerfile.prod
docker images loan-api
```

```text
FROM python:3.12-slim AS builder
FROM python:3.12-slim
IMAGE           ID             DISK USAGE   CONTENT SIZE   EXTRA
loan-api:prod   6a0c9430752f        774MB          175MB
```

## 2. Multi-stage build

Two `FROM` lines: a builder stage and a clean runtime stage. Only the venv, model and app files are copied into the final image.

```bash
grep -n "FROM\|COPY --from" Dockerfile.prod
```

```text
2:FROM python:3.12-slim AS builder
12:FROM python:3.12-slim
16:COPY --from=builder /opt/venv /opt/venv
17:COPY --from=builder /app/model.joblib .
```

## 3. Dev dependencies separated

`pytest` is only in `requirements-dev.txt`, not in the production list.

```bash
grep pytest requirements.txt
cat requirements-dev.txt
pytest -v
```

```text
(grep prints nothing, exit code 1)
-r requirements.txt
pytest==9.1.1
...
================== 5 passed, 15 warnings in 71.71s (0:01:11) ==================
```

The 15 warnings are scikit-learn `InconsistentVersionWarning`s from the model file, which was pickled with an older version; they do not affect the tests.

## 4. Runs as a non-root user

```bash
docker run -d --name prod -p 8000:8000 loan-api:prod
docker exec prod whoami
```

```text
appuser
```

## 5. HEALTHCHECK

```bash
sleep 35
docker ps --filter name=prod
docker rm -f prod
```

```text
CONTAINER ID   IMAGE           COMMAND                  CREATED          STATUS                    PORTS                    NAMES
1b4a3863a92e   loan-api:prod   "fastapi run main.py…"   39 seconds ago   Up 41 seconds (healthy)   0.0.0.0:8000->8000/tcp   prod
```

## 6. Pinned versions and configurable MODEL_PATH

```bash
cat requirements.txt
grep -n MODEL_PATH main.py
curl http://localhost:8000/health
```

```text
fastapi[standard]==0.150.0
scikit-learn==1.9.1
pandas==3.0.6
numpy==2.5.4
joblib==1.6.0
14:MODEL_PATH = os.getenv("MODEL_PATH", "model.joblib")
18:    ml.update(joblib.load(MODEL_PATH))
{"status":"ok","model_version":"1.0.0"}
```

## 7. Vulnerability scan (Trivy 0.69.3, pinned)

```bash
docker build --pull -f Dockerfile.prod -t loan-api:prod .
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:0.69.3 image --severity HIGH,CRITICAL loan-api:prod
```

Result: 0 findings in Python packages; HIGH findings only in Debian 13.7 OS packages (the `python:3.12-slim` base). No CRITICAL findings. The full table is long, so the unique CVEs are listed below.

### Notes on HIGH/CRITICAL findings

The image was rebuilt with `docker build --pull` against the latest base image. Trivy reports no fixed version for any of these (status `affected` or `fix_deferred`), so none can be fixed by rebuilding or upgrading yet. They are in the Debian base layer, not in application code. The container runs as non-root and the packages named are not used by the API at runtime. Re-scan after each base-image update.

- `CVE-2025-69720` (ncurses-base, ncurses-bin, libncursesw6, libtinfo6): no fix available; terminal library, not used by the API.
- `CVE-2026-119373` (libsqlite3-0): no fix available; the API does not use SQLite.
- `CVE-2026-16742` (libsystemd0, libudev1): no fix available; no systemd runs in the container.
- `CVE-2026-54369` (libacl1): no fix available; not exposed to network input.
- `CVE-2026-76642`, `CVE-2026-78408`, `CVE-2026-78409`, `CVE-2026-78410` (util-linux, mount, login, bsdutils, libmount1, libblkid1, libuuid1, libsmartcols1, liblastlog2-2): no fix available; they concern mount and nsenter, which are not used, and the container runs unprivileged.
- `CVE-2026-9538` (perl-base): fix deferred by Debian; Perl is not used by the API.

## Extra: Compose stack and data persistence

```bash
docker compose up -d --build
docker compose ps
docker compose exec db psql -U loans -d loans -c "SELECT id, status FROM loan_applications WHERE id=101;"
docker compose exec db psql -U loans -d loans -c "UPDATE loan_applications SET status='approved' WHERE id=101;"
docker compose down && docker compose up -d
docker compose exec db psql -U loans -d loans -c "SELECT id, status FROM loan_applications WHERE id=101;"
```

```text
NAME                 IMAGE           SERVICE   STATUS
loan-api-adminer-1   adminer:4.8.1   adminer   Up 22 seconds
loan-api-api-1       loan-api-api    api       Up 14 seconds (health: starting)
loan-api-db-1        postgres:17     db        Up 24 seconds (healthy)

 id  | status
-----+---------
 101 | pending

UPDATE 1

-- after down + up (data persists):
 id  |  status
-----+----------
 101 | approved
```

## Extra: Published image runs from the registry

```bash
docker rmi sprows/loan-api:1.0.0 sprows/loan-api:latest
docker run --rm -p 8000:8000 sprows/loan-api:1.0.0
```

Pulled from Docker Hub (digest `sha256:6a0c9430...c77fe`), `/health` returned `{"status":"ok","model_version":"1.0.0"}`, `/docs` returned HTTP 200, and a prediction returned HTTP 200.

Screenshot of `/docs` with the 200 response: `screenshots/docs-200.png`

## Secrets

```bash
grep -rniE "password|secret|token|api_key" . --exclude=CHECKLIST.md --exclude-dir=__pycache__
```

```text
./compose.yaml:18:      POSTGRES_PASSWORD: loans_dev_only   # development only; never commit real passwords
```

Only the allowed development-only database password appears.
