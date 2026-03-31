# PC Build Tracker

Track prices for your entire PC build across Newegg, Best Buy, Amazon,
Micro Center, and B&H Photo. Get Discord and email alerts when any part
drops below your target price.

## Features
- Track unlimited parts across any category
- Price history charts per part
- Build cost summary and budget tracker
- Discord + email alerts with deal logic
- "Multiple deals" summary alert when several parts drop at once
- All data stored locally on your NAS in SQLite

## Deploy with Dockge

Paste this into a new Dockge stack (replace YOURUSERNAME):

```yaml
services:
  backend:
    build:
      context: https://github.com/YOURUSERNAME/pc-build-tracker.git#main:backend
    container_name: pc-build-tracker-api
    restart: unless-stopped
    volumes:
      - ./config:/config
    environment:
      DB_PATH: /config/tracker.db

  frontend:
    build:
      context: https://github.com/YOURUSERNAME/pc-build-tracker.git#main:frontend
    container_name: pc-build-tracker-ui
    restart: unless-stopped
    ports:
      - "8080:80"
    depends_on:
      - backend
```

Then open http://YOUR_NAS_IP:8080

## First-time setup
1. Go to **Settings** — add your Discord webhook and/or email
2. Go to **Parts List** — add each part you're tracking with a target price
3. Click **Check Prices Now** in the header to run your first check
4. Come back to **Dashboard** to see results and price history charts

## Updating
Push changes to GitHub, then in Dockge click **Rebuild**.
