
## Future Production Infrastructure
The following features have been explicitly quarantined from the MVP scope to prevent over-engineering and database lock contention:
- OpenTelemetry (API, FastAPI instrumentation, OTLP exporter)
- Circuit Breakers (`pyresilience`)
- Dead Letter Queues (DLQ) and exponential backoff retry semantics
- Graceful SIGTERM draining for the worker polling loop
