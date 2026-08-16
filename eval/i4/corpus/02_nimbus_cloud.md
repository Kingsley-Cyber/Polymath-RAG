### Nimbus Cloud Platform: Postmortem Review

Nimbus Cloud uses Kubernetes to orchestrate its container platform. The Ledger billing service depends on the Postgres cluster for ledger writes. The operations group manages the fleet from a single console.

The Nimbus billing service is part of the Nimbus Cloud platform. The engineering group created the load-testing harness after the September outage. The outage summary is described in the Nimbus postmortem report.

The team considered replacing the cache layer but kept the existing setup. The Postgres cluster was not the root cause of the outage. The Nimbus API gateway is implemented in Go. The platform was designed by the engineering group. They deployed the patch and restarted the cluster.
