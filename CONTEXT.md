# Vibe Memory

Vibe Memory stores recollections and relations so an agent can recover context across conversations.

## Language

**Causal relation**:
One event or condition produces another. Its direction is cause → effect; a later observation of the cause does not reverse that direction.
_Avoid_: causal continuation, mere succession

**Temporal adjacency**:
Two recollections occur next to each other in an account or conversation. Adjacency alone says nothing about causation.
_Avoid_: causal relation

**Diagnostic association**:
A symptom or observation points to a possible explanation. It can guide a search for a cause but does not assert that the symptom caused the explanation.
_Avoid_: causal relation

**Resolution relation**:
An action addresses a problem or symptom. It is distinct from the condition that caused the problem.
_Avoid_: causal relation

**Edge provenance**:
The origin of a proposed relation, such as an automatic rule, model judgment, or explicit caller assertion. Provenance alone does not establish that the relation or its direction is true.
_Avoid_: causal verification

**Causal direction verification**:
An independent check against the underlying account that the named source condition produced the named target outcome. A confidence score or edge provenance is not this check.
_Avoid_: edge confidence, edge provenance
