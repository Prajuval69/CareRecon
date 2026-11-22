# Human review workflow

Finding statuses OPEN -> ACKNOWLEDGED -> RESOLVED or WAIVED; allow only documented permitted transitions, including re-open if rationalized. `review` CLI takes finding ID, new status, actor and rationale; actor and rationale required and visible in report. Each transition creates append-only review_event record. Original rule finding is never deleted or overwritten by a waiver.

Mock review users only; this is not enterprise authentication or regulatory workflow. Use a local demo actor such as `demo-analyst`. Show unresolved, acknowledged and waived findings separately. Test invalid transitions, missing reason, repeat commands and audit chronology.
