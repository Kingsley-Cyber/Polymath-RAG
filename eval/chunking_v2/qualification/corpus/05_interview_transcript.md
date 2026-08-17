# Platform Engineering Interview: Session 7

## Participant Background

The participant is a staff engineer with eleven years in payments infrastructure. They joined the platform group after four years on the core ledger team. Their daily work spans capacity planning, incident response, and the internal developer platform.

## Transcript

Interviewer: When you joined, what was the state of the deployment pipeline?

Participant: Honestly, fragile. We had a single deployment lane shared by forty services. A flaky test anywhere froze everyone. The first thing I did was introduce per-lane isolation, which sounds obvious now but required a budget conversation.

Interviewer: How did the budget conversation go?

Participant: Slow but civil. I brought queue data. When you show leadership that a single lane costs eleven engineer-hours a week in waiting, the argument makes itself. We got the budget in the second quarter.

Interviewer: What failed after that?

Participant: Cache stampedes, twice. The lanes were isolated but the artifact cache was shared. A large build would evict everything. We fixed it with content-addressed storage and a reservation queue. The lesson was that isolation is systemic, not local.

Interviewer: How do you measure platform success now?

Participant: Lead time for change, change failure rate, and time to restore. We publish them monthly. The numbers moved slowly for two quarters, then compounded. I attribute that to trust: once teams believed the platform would not eat their weekend, they routed more through it.

## Analyst Notes

The transcript shows a recurring theme: infrastructure wins by making waiting visible. Queue times, eviction counts, and restore hours were all converted into budget arguments. The participant's style is to instrument first and negotiate second.
