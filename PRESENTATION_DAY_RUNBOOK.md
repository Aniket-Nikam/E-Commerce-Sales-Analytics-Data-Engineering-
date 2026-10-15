# Presentation Day Runbook

Use this sequence for the practical case study demonstration. The important rule is to use Docker mode when you claim that RabbitMQ and live streaming are running.

## Prepare tonight

1. Connect the laptop to the internet and power supply.
2. Open Docker Desktop and wait until the Docker engine reports that it is running.
3. Open PowerShell in the project folder.
4. Run the read-only startup audit:

```powershell
.\Start_ECommerce_Platform.ps1 -CheckOnly
```

5. Build and start the complete demonstration once so images and Python packages are cached:

```powershell
.\Start_ECommerce_Platform.ps1 -Mode Docker
```

6. Confirm that these pages open:

- Dashboard: http://127.0.0.1:8501
- FastAPI documentation: http://127.0.0.1:8001/docs
- RabbitMQ management: http://127.0.0.1:15672
- RabbitMQ login: `ecommerce` / `ecommerce-demo`

7. Stop the stack cleanly after the rehearsal:

```powershell
docker compose --profile demo down
```

Do not add `--volumes`; keeping the volumes makes tomorrow's startup faster and preserves demonstration data.

## Start tomorrow

1. Start the laptop at least 15 minutes before the presentation.
2. Start Docker Desktop and wait for the engine to become ready.
3. Double-click `Start_ECommerce_From_Desktop.cmd` in the project folder.
4. For a strict live-mode check, use PowerShell instead:

```powershell
.\Start_ECommerce_Platform.ps1 -Mode Docker
```

5. Wait until the launcher reports that the real-time API and RabbitMQ consumer are healthy.
6. Keep three browser tabs ready: Streamlit, FastAPI `/docs`, and RabbitMQ management.

## Prove that the system is live

1. On the Streamlit live panel, note the current event count and revenue.
2. Open RabbitMQ management and show the `ecommerce.order.events.demo` queue.
3. In FastAPI `/docs`, open `POST /orders`, click **Try it out**, submit one valid order, and confirm the HTTP 202 response.
4. Explain that HTTP 202 means RabbitMQ accepted the message for asynchronous processing; it does not mean the dashboard already refreshed.
5. Show the RabbitMQ queue activity and wait up to five seconds for Streamlit's next poll.
6. Return to Streamlit and show that the event count, recent-order table, or live revenue changed.

The live path is:

```text
Order simulator or POST /orders
    -> FastAPI validation
    -> RabbitMQ durable queue
    -> Python consumer
    -> idempotent DuckDB insert
    -> FastAPI metrics
    -> Streamlit refresh every five seconds
```

Describe this as near real time, not strict hard real time, because the dashboard polls every five seconds and no fixed latency deadline is guaranteed.

## Useful checks

```powershell
docker compose --profile demo ps
docker compose logs --tail 50 rabbitmq
docker compose logs --tail 50 realtime-api
docker compose logs --tail 50 dashboard
```

Healthy endpoints:

```text
http://127.0.0.1:8001/health
http://127.0.0.1:8501/_stcore/health
```

## If something fails

- If Docker is not ready, restart Docker Desktop and wait for the Linux engine before retrying.
- If port 8501, 8001, or 15672 is occupied, stop the older process or container before starting the stack.
- If the dashboard says that real-time service is offline, do not present the page as a live run. Check `docker compose --profile demo ps` and the logs first.
- Local mode can still demonstrate historical DuckDB analytics, but RabbitMQ streaming is not active in that mode.
- Keep the PPT and report available offline in case the classroom internet is unavailable.

## Shut down after the demonstration

```powershell
docker compose --profile demo down
```
