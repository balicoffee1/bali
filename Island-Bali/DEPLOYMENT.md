# Island Bali backend deployment

This runbook describes the current production deployment on Reg.Cloud.
It intentionally contains no password, private key, token, or `.env` value.

## Production layout

- SSH host: `root@79.174.81.151`
- Application directory: `/root/bali/Island-Bali`
- Python environment: `/root/bali/Island-Bali/myvenv`
- HTTP service: `island_bali.service` (Gunicorn)
- WebSocket service: `island_bali_ws.service` (Daphne on `127.0.0.1:8001`)
- Worker services: `island_bali_celery.service` and
  `island_bali_celery_beat.service`
- Reverse proxy: `nginx.service`

The production checkout currently contains local changes and untracked files.
Do not run `git reset`, `git clean`, or blindly replace the application directory.
For a focused hotfix, deploy only the reviewed files and keep a timestamped backup.

## Focused backend hotfix

Run the relevant tests locally first:

```sh
docker compose build ws
docker compose run --rm --no-deps ws \
  python manage.py test --noinput orders.tests_realtime
```

Inspect the production target before copying anything:

```sh
ssh root@79.174.81.151 \
  'systemctl is-active island_bali_ws.service && \
   stat /root/bali/Island-Bali/path/to/file.py'
```

Create a uniquely named backup directory and copy each target file into it. Use
an explicit directory name so rollback never depends on an unresolved glob:

```sh
ssh root@79.174.81.151 \
  'mkdir -p /root/deploy-backups/YYYYMMDDTHHMM-description && \
   cp -a /root/bali/Island-Bali/path/to/file.py \
     /root/deploy-backups/YYYYMMDDTHHMM-description/file.py'
```

Upload to a temporary path, then install the reviewed file atomically enough for
this single-host deployment:

```sh
scp path/to/file.py root@79.174.81.151:/tmp/file.py.new
ssh root@79.174.81.151 \
  'install -m 0644 /tmp/file.py.new \
     /root/bali/Island-Bali/path/to/file.py && \
   rm /tmp/file.py.new'
```

Validate before restarting:

```sh
ssh root@79.174.81.151 \
  'cd /root/bali/Island-Bali && \
   myvenv/bin/python manage.py check'
```

Restart every long-running process that imports the changed code. Consumer-only
changes require Daphne; HTTP view-only changes require Gunicorn. Shared
serializers and realtime publisher code are imported by both the WebSocket
snapshot producer and the HTTP workers that publish deltas, so restart both:

```sh
ssh root@79.174.81.151 \
  'systemctl restart island_bali.service island_bali_ws.service && \
   systemctl is-active island_bali.service island_bali_ws.service'
```

When a Celery task module changes, restart the worker too; otherwise the old
worker will not register the new task name:

```sh
ssh root@79.174.81.151 \
  'systemctl restart island_bali_celery.service && \
   systemctl is-active island_bali_celery.service'
```

After deployment, inspect the service and application logs:

```sh
ssh root@79.174.81.151 \
  'journalctl -u island_bali_ws.service --since "5 minutes ago" --no-pager'
```

For the staff-order WebSocket specifically, a successful connection must log
`ws_snapshot_sent` followed by `ws_shop_snapshot_sent`, remain connected, and
must not log `Exception inside application` or close with code `1011`.

## Rollback

Copy the exact backed-up file back, validate it, and restart the same service:

```sh
ssh root@79.174.81.151 \
  'cp -a /root/deploy-backups/YYYYMMDDTHHMM-description/file.py \
     /root/bali/Island-Bali/path/to/file.py && \
   cd /root/bali/Island-Bali && \
   myvenv/bin/python manage.py check && \
   systemctl restart island_bali.service island_bali_ws.service && \
   systemctl is-active island_bali.service island_bali_ws.service'
```

Do not delete the backup until production behavior has been verified.

## Admin panel (React SPA) deploy

The web admin panel is a static build served by nginx from
`/var/html/admin-panel` (see `location /` in
`/etc/nginx/sites-enabled/island_bali`). There is no build step on the server —
build locally and upload `dist/`.

Build and check the bundle locally:

```sh
npm --prefix admin-panel run build
```

Back up the live directory, upload into a staging directory, then swap:

```sh
TS=$(date +%Y%m%dT%H%M)
ssh root@79.174.81.151 \
  "mkdir -p /root/deploy-backups/${TS}-admin-panel && \
   cp -a /var/html/admin-panel /root/deploy-backups/${TS}-admin-panel/ && \
   rm -rf /var/html/admin-panel.new && mkdir -p /var/html/admin-panel.new"

scp -r admin-panel/dist/. root@79.174.81.151:/var/html/admin-panel.new/

ssh root@79.174.81.151 \
  'chmod -R a+rX /var/html/admin-panel.new && \
   mv /var/html/admin-panel /var/html/admin-panel.old && \
   mv /var/html/admin-panel.new /var/html/admin-panel && \
   nginx -t && systemctl reload nginx'
```

Asset filenames are content-hashed, so the swap plus a reload is enough; no
service restart is required and the Django services are untouched.

Verify that the served files match what was built locally:

```sh
shasum -a 256 admin-panel/dist/index.html admin-panel/dist/assets/*
ssh root@79.174.81.151 'cd /var/html/admin-panel && sha256sum index.html assets/*'
```

Roll back by moving `/var/html/admin-panel.old` (or the timestamped backup)
back into place and reloading nginx.
