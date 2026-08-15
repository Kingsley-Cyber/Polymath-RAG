# Transcript: Retrieval Lecture

Instructor: Retrieval systems combine several lanes. The document lane routes, the parent lane localizes, and the child lane retrieves exact passages.

Student: Which lane protects recall when routing fails?

Instructor: The global child lane. A child hit survives even when its document scores zero.

Student: And how do the lanes merge?

Instructor: Reciprocal rank fusion over the rankings, not the raw scores. The scales are not comparable, so fusion uses ranks only.
