# Platform Services and Contracts

Platform services expose versioned contracts over the network. Every cross-process payload conforms to a schema, and private package imports never cross process boundaries.

A service owns one responsibility. One process owns user intake and reads; another owns scheduling; workers own single durable stages; stores own persistence engines.

Contracts change through versioning, not mutation. A contract bump is a new version with explicit compatibility, and every reverse dependent is verified before the new version activates.

The platform keeps model processes host-native. Models never run inside containers, and one sidecar process loads one model release.
