# HarborPay Billing Operations Guide

## Invoice Lifecycle

An invoice is created the moment a subscription period closes. The billing engine computes usage, applies proration, adds tax, and issues the invoice atomically. From there the invoice moves through issued, sent, paid, or disputed states. Every transition writes an immutable ledger entry that the reconciliation jobs read.

Failed payments enter a dunning cycle. The retry schedule is exponential with a fourteen-day horizon. Customers can clear a failed invoice at any point in the cycle, and the ledger records the recovery event separately from the original attempt.

## Disputes and Chargebacks

A dispute freezes the disputed amount but never the customer relationship. Support triages disputes into billing error, service dissatisfaction, and fraud. Billing errors are corrected with credit notes. Service dissatisfaction routes to the retention team. Fraud routes to the risk team and suspends the account pending review.

Chargebacks arrive from the card network with a deadline. The evidence package assembles automatically from the ledger, the delivery logs, and the acceptance records. HarborPay wins roughly seventy percent of chargeback cases where delivery evidence exists.

## Month-End Close

The close sequence is strict. First the usage pipeline must finish. Second the ledger recon must report zero drift. Third the revenue recognition job runs. Fourth the finance export is cut. Any failure in the sequence halts the close and pages the billing on-call.

> The close is not finished until the finance export is reconciled against the ledger to the cent.

The quotation above is the operational rule. Teams have attempted partial closes during incidents; each attempt produced a reconciliation backlog that outlasted the incident.

## Appendix: Retry Schedule

| day | action |
| --- | --- |
| 0 | initial charge |
| 1 | retry |
| 3 | retry + email |
| 7 | retry + dunning notice |
| 14 | final attempt + suspension |

The schedule above applies to card payments only. Bank-debit retries follow a separate calendar.
