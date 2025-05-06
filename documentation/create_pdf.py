from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Content of the guide
guide = """Podman & Podman Compose Guide

Prerequisites:
- Working directory: Run all commands from the folder containing your docker-compose.yml \\FuzzyPrompts.
- Installed & configured: Podman and podman-compose, plus a running Podman machine via your start_fuzzy_podman.ps1.

1. Start & Update
1.1 Safe Start & Rebuild (background, rebuilds changed services):
podman-compose -f docker-compose.yml up --build -d

1.2 Quick Start (background, no rebuild):
podman-compose -f docker-compose.yml up -d

1.3 Foreground (debug, logs attached):
podman-compose -f docker-compose.yml up --build

2. Stop & Cleanup
2.1 Full Stop & Remove (keep data):
podman-compose -f docker-compose.yml down

2.2 Stop, Remove & Delete Data (volumes):
podman-compose -f docker-compose.yml down --volumes

2.3 Pause Only (stop):
podman-compose -f docker-compose.yml stop
Restart with:
podman-compose -f docker-compose.yml start

3. Status & Logs
podman-compose -f docker-compose.yml ps
podman ps -a
podman-compose -f docker-compose.yml logs -f
podman-compose -f docker-compose.yml logs web
podman-compose -f docker-compose.yml logs -f db

4. Code Changes
# Templates/Static reload on refresh.
# Python code changes: restart services:
podman-compose -f docker-compose.yml restart web
podman-compose -f docker-compose.yml restart web worker
# Dependencies:
podman-compose -f docker-compose.yml up --build -d web worker

5. Database Migrations
podman-compose -f docker-compose.yml exec web flask db migrate -m "Your message"
podman-compose -f docker-compose.yml exec web flask db upgrade
podman-compose -f docker-compose.yml exec web flask db current

6. Exec Into Containers
podman-compose -f docker-compose.yml exec web bash
podman-compose -f docker-compose.yml exec db bash
podman-compose -f docker-compose.yml exec db psql -U $DB_USER -d $DB_NAME

7. Volume Management
podman volume ls
podman volume inspect promptplayground_postgres_data
podman volume rm promptplayground_postgres_data

8. System Cleanup
podman image prune
podman volume prune
podman system prune -a --volumes
"""

# Create the PDF
pdf_path = "./podman_compose_guide.pdf"
c = canvas.Canvas(pdf_path, pagesize=letter)
width, height = letter
margin = 72
y = height - margin

for line in guide.split("\n"):
    c.drawString(margin, y, line)
    y -= 14
    if y < margin:
        c.showPage()
        y = height - margin

c.save()

# Provide link to the user
pdf_path
