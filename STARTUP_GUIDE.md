# One-click startup guide

Double-click **Start E-Commerce Analytics.cmd** on the Windows Desktop. The launcher records every startup decision in `results/logs/startup.log` and follows this sequence:

1. Find Docker and validate `docker-compose.yml`.
2. Start Docker Desktop when its Linux engine is not already ready.
3. Start RabbitMQ, FastAPI, the embedded consumer, the event simulator, and Streamlit.
4. Wait for the API and dashboard health endpoints instead of opening a half-started application.
5. Open `http://127.0.0.1:8501` only after the dashboard responds.
6. If Docker cannot start, clearly report that strict streaming is offline and fall back to the historical DuckDB dashboard.

## Modes

Run these from PowerShell in the project directory:

```powershell
# Automatic: prefer strict real time, fall back to historical analytics
.\Start_ECommerce_Platform.ps1

# Require the RabbitMQ real-time stack; fail instead of falling back
.\Start_ECommerce_Platform.ps1 -Mode Docker

# Historical DuckDB dashboard only
.\Start_ECommerce_Platform.ps1 -Mode Local

# Read-only startup audit; does not start or stop anything
.\Start_ECommerce_Platform.ps1 -CheckOnly
```

## URLs in strict real-time mode

- Dashboard: `http://127.0.0.1:8501`
- FastAPI and interactive API documentation: `http://127.0.0.1:8001/docs` (mapped to container port `8000`)
- RabbitMQ management: `http://127.0.0.1:15672`
- Classroom RabbitMQ login: `ecommerce` / `ecommerce-demo`

The simulator publishes one order per second. Streamlit reloads its live section every five seconds.

## Stop the platform

```powershell
docker compose --profile demo down
```

The RabbitMQ and analytics Docker volumes remain available for the next run. Add `--volumes` only if you deliberately want to delete that persisted demonstration data.

## Current machine note

The launcher reports strict real-time mode as active only after `http://127.0.0.1:8001/health` responds. Port `8001` is used on Windows because another local application may already own port `8000`; containers and Kubernetes continue to use port `8000` internally. If Docker still fails, use Docker Desktop's **Troubleshoot** page to repair or reset the engine, then run the launcher again.

