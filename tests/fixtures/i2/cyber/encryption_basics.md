# Encryption Basics

Encryption protects data confidentiality at rest and in transit. Data at rest is encrypted on disk; data in transit is encrypted by transport protocols such as TLS.

Keys must be managed separately from the data they protect. A system that stores the key next to the ciphertext gains little from encryption.

Authenticated encryption binds confidentiality and integrity. The receiver can verify that the ciphertext was not modified, which prevents a class of tampering attacks.

Encryption does not remove the need for access control. Authorized users can still mishandle plaintext, and monitoring remains necessary to detect misuse.
