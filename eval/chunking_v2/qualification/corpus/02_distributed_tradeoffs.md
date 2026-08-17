# Consistency Models in Practice

## Why Consistency Matters

Every distributed datastore chooses a position on the consistency spectrum, and every position is a set of tradeoffs rather than a virtue. Strong consistency simplifies application logic but constrains availability during partitions. Eventual consistency maximizes availability but pushes conflict handling into the application. Session consistency and causal consistency occupy the middle ground, and most production systems quietly implement one of these rather than the extremes they advertise.

## Read-Your-Writes in Practice

Session consistency guarantees that a client observes its own writes. This sounds trivial until a gateway load-balances requests across regions. If a write lands in the eastern region and the next read is served from the western replica, the client's own update vanishes from view. Session tokens solve this by tagging each request with a logical clock that replicas consult before serving.

The cost of session tokens is modest but real. Every request carries the token, replicas must track acknowledged offsets, and token loss degrades silently back to eventual consistency. Teams that adopt session consistency should instrument the degradation path explicitly.

## Causal Consistency and False Sharing

Causal consistency preserves the happens-before relationship between operations that communicate through the client. Two independent writers on different keys never block each other. The classic failure mode is false sharing: an application assumes ordering that the model does not provide because the ordering was never expressed through a causal channel.

Consider a ticketing workflow. One process reserves a seat, then messages a second process to print the badge. If the badge printer reads from a replica that has not applied the reservation, the badge prints for a seat that is not held. The bug is not in the datastore; the bug is that the application expressed causality through an out-of-band channel.

## Choosing Deliberately

- write down the invariants the application actually needs
- pick the weakest model that satisfies them
- instrument every degradation path
- rehearse partition behavior in game days

Teams that follow this sequence rarely regret their consistency choice. Teams that pick a model by vendor marketing usually discover the missing guarantee in production.
