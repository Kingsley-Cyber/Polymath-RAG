# Meridian Platform Incident Review

## Executive Summary

On March 4 the Meridian identity platform suffered a nine-minute outage during a routine certificate rotation. The rotation job replaced the signing key before the verification fleet had warmed its cache, so tokens signed with the new key were rejected wholesale. Monitoring caught the rejection spike within forty seconds and the platform team rolled the rotation back manually.

The incident was contained quickly but exposed three structural weaknesses. First, the rotation job had no staged rollout. Second, the verification fleet cached the public key set with no negative-cache escape hatch. Third, the alerting threshold for token rejection was tuned so conservatively that a real outage barely cleared it.

## Timeline

The rotation began at 14:02 UTC. At 14:03 the first rejection spike appeared in the token-service metrics. The on-call engineer acknowledged the page at 14:04 and began triage. By 14:07 the team identified the signing-key mismatch as the cause. The rollback completed at 14:11 and error rates returned to baseline within a minute.

## Root Cause Analysis

The rotation service and the verification service disagreed about ordering. The rotation service treated key publication as atomic. The verification service treated key retrieval as lazy. Neither contract was written down, and both teams were right about their own half. The fix is a versioned key-rotation protocol where publication is two-phase and verification fleets subscribe to rotation events instead of polling.

Cache behavior amplified the fault. Once a verifier fetched an empty or partial key set, it cached that result for five minutes. During those five minutes every token validated by that instance failed. A negative-result TTL of five seconds would have converted a hard outage into a soft degradation.

## Remediation Actions

| action | owner | due |
| --- | --- | --- |
| two-phase key publication | identity team | Q2 |
| negative-cache TTL reduction | platform team | Q2 |
| rejection-rate alert retune | SRE | Q3 |

The remediation plan is tracked in the incident register. Each item carries an owner and a review date. The identity team will present the two-phase protocol design at the next architecture council.

## Lessons for Reviewers

Rotation is a distributed-systems problem, not a configuration problem. Anywhere a fleet caches authority data, the rotation path must be rehearsed. The platform team now runs a quarterly game day that rotates production keys under supervision.

```text
rotation: publish -> warm -> verify -> commit
observed: publish -> commit -> (fleet still cold)
```

The observed sequence above is what the fleet actually executed. Reviewers should compare it against the intended protocol when reading the timeline.
