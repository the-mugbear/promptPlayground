# Podman & Podman-Compose Guide for `fuzzy_prompts`

**Assumptions**

* You are running these commands from the directory containing your `docker-compose.yml` file (e.g., `..\FuzzyPrompts`).
* You have Podman and podman-compose installed and configured.
* You have a Podman machine running (as handled by your `start_fuzzy_podman.ps1` script).

---

## 1. Starting Your Application

### 1.1 Safe Start & Update

```bash
podman-compose -f docker-compose.yml up --build -d
```

### 1.2 Just Starting (no rebuild)

```bash
podman-compose -f docker-compose.yml up -d
```

### 1.3 Foreground (for debugging)

```bash
podman-compose -f docker-compose.yml up --build
```

### 1.4 Via Your Script

```powershell
.\start_fuzzy_podman.ps1
```

---

## 2. Stopping Your Application

* **Full cleanup** (keeps volumes):

  ```bash
  podman-compose -f docker-compose.yml down
  ```
* **Remove volumes too** (data loss!):

  ```bash
  podman-compose -f docker-compose.yml down --volumes
  ```
* **Pause only** (stops containers but keeps network & volumes):

  ```bash
  podman-compose -f docker-compose.yml stop
  ```

---

## 3. Checking Status and Viewing Logs

* **List running services**:

  ```bash
  podman-compose -f docker-compose.yml ps
  ```
* **List all containers**:

  ```bash
  podman ps -a
  ```
* **Follow all logs**:

  ```bash
  podman-compose -f docker-compose.yml logs -f
  ```
* **Logs for a specific service** (e.g., web or db):

  ```bash
  podman-compose -f docker-compose.yml logs web
  podman-compose -f docker-compose.yml logs -f db
  ```

---

## 4. Handling Web Application Code Changes

* **Template/Static File Changes**: Changes to `templates/` or `static/` are reflected on refresh thanks to mounted volumes.
* **Python Code Changes**: Gunicorn + Flask's reloader may not always pick up changes. For reliability, restart services:

  ```bash
  podman-compose -f docker-compose.yml restart web
  # or both web and worker:
  podman-compose -f docker-compose.yml restart web worker
  ```
* **Dependency Changes (**\`\`**)**: Rebuild images:

  ```bash
  podman-compose -f docker-compose.yml up --build -d web worker
  ```

---

## 5. Handling Database Schema Changes (Migrations)

1. **Generate migration**:

   ```bash
   podman-compose -f docker-compose.yml exec web flask db migrate -m "Description"
   ```
2. **Review**: Check `migrations/versions/` for correctness.
3. **Apply migration**:

   ```bash
   podman-compose -f docker-compose.yml exec web flask db upgrade
   ```
4. **Verify**:

   ```bash
   podman-compose -f docker-compose.yml exec web flask db current
   ```

---

## 6. Executing Commands Inside Containers

* **Shell access**:

  ```bash
  podman-compose -f docker-compose.yml exec web bash
  podman-compose -f docker-compose.yml exec db bash
  ```
* **PostgreSQL CLI**:

  ```bash
  podman-compose -f docker-compose.yml exec db psql -U ${DB_USER} -d ${DB_NAME}
  ```

---

## 7. Managing Data (Volumes)

* **List volumes**:

  ```bash
  podman volume ls
  ```
* **Inspect**:

  ```bash
  podman volume inspect promptplayground_postgres_data
  ```
* **Remove** (data loss!):

  ```bash
  podman volume rm promptplayground_postgres_data
  ```

---

## 8. Cleaning Up Resources

* **Stop & remove services** (keep volumes):

  ```bash
  podman-compose -f docker-compose.yml down
  ```
* **Stop, remove & volumes** (data loss!):

  ```bash
  podman-compose -f docker-compose.yml down --volumes
  ```
* **Prune images**:

  ```bash
  podman image prune
  ```
* **Prune volumes**:

  ```bash
  podman volume prune
  ```
* **Full system prune** (caution!):

  ```bash
  podman system prune -a --volumes
  ```

---

## Tips for VS Code

* Split the editor: Ctrl+\</kbd>
* Open Markdown preview: Ctrl+Shift+V
