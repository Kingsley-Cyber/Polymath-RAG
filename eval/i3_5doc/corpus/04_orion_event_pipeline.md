### Orion Analytics Event-Pipeline Recovery Review

Orion Analytics operates an Order Event Router that receives checkout events from the Atlas Commerce Platform. The router publishes order-created and order-updated events to Apache Kafka, while PostgreSQL stores the authoritative order state. A Redis cache is used for short-lived idempotency keys. The service runs on Kubernetes in Orion Analytics' production environment.

On 11 August 2026, a consumer deployment introduced a retry bug that caused several Kafka messages to be processed more than once. PostgreSQL did not duplicate the underlying orders, but downstream notification workers sent duplicate confirmation messages because they treated every delivery as a new event. Engineers traced the problem to a retry path that acknowledged the Kafka message after executing the notification instead of before committing the idempotency record.

Orion Analytics changed the consumer so that the idempotency record is committed before the notification is dispatched. The team retained Kafka, PostgreSQL, Redis, and Kubernetes; none of those platforms was identified as the root cause. The engineering group also added a replay fixture to the Reliable Event Processing Runbook and now verifies duplicate delivery during deployment testing.
