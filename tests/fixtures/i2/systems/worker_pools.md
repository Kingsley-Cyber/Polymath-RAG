# Worker Pools and Task Queues

A worker pool is a fixed set of processes that consume tasks from a shared queue. Each worker owns one durable stage of processing; the system as a whole moves documents through a sequence of stages.

Backpressure matters when the queue grows faster than workers drain it. The system must bound how quickly work is submitted so that no single component is overwhelmed.

Workers poll the queue for undelivered events and mark each event as delivered when claimed. If a worker fails before completing its stage, the event can be redelivered because the idempotency key makes repeated processing safe.

The model treats every mutation as content-addressed. Replaying identical input must not create a second logical result, so every stage commits through receipts that record what was written.
