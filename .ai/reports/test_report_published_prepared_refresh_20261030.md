# Published prepared PR base refresh

macOS maintenance development, task published-pr-prepared-refresh-20261030-e5a9d2f0,
base db2ae9a48ceca365852072e622aa6627aa7d0b83.

An existing published PR could refresh once, remain prepared, and then become
unable to adopt another master advance. The existing prepare operation now
accepts that exact state only with a valid distinct recorded published head.
It retains the original PR, snapshot history and repair counter, and rechecks
remote base, PR head, feature/candidate graph and receipt before atomic update.

Worker RED reproduced the rejected legitimate transition. Scoped Node24 tests
passed 25/25, including rejection when PR head points at the prior unpublished
candidate. Initial full Git safety run passed 127/127 before that final negative
case was added; final candidate validation remains pending. Independent review
found no P1 and requested that negative case, now added. Real PR245 ledger has
not been mutated. No deployment, cleanup, model or account operation is performed
by this patch. Full Router, exact candidate review and CI remain required.

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"The existing Git delivery prepare operation gains a narrowly validated published prepared transition; no service, execution engine, deployment authority or cleanup gate is added.","diagrams":[]} -->
