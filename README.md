
# nas_drop_bot (scaffold)

A minimal Telegram bot running in Docker (WSL2 backend). It mounts the **entire D: drive from Windows** into the container at `/mnt/d`, so both:

- `/mnt/d/Downloads/`
- `/mnt/d/Plex Library/`

are on **the same filesystem**, enabling instant atomic renames between those folders.

## Quick start

1. Copy `.env.example` to `.env` and set `TELEGRAM_BOT_TOKEN`.
2. From the project root, run (on the host with Docker Desktop + WSL2):
   ```bash
   docker compose up --build -d
   ```
3. The bot will respond **OK** to any message it receives.

## Dev Containers

Open this folder in VS Code and choose **Dev Containers: Reopen in Container**.
This uses the `docker-compose.dev.yml` override to mount your source for hot-reload.

## Add more services

In `docker-compose.yml`, see the comment `# (add more services here later)` — append other containers to the same compose project.
