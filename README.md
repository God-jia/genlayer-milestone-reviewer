# GenLayer Milestone Reviewer

A DAO grant reviewer that reads evidence instead of trusting links, built as a
**GenLayer Intelligent Contract**.

A grant owner writes acceptance criteria in full. Contributors submit milestones
with a summary and an evidence URL. Reviewing a milestone renders that page,
scores the work against the criteria, and returns `pass` / `partial` / `fail`
plus a 0–100 score and short findings. The result is committed **only after
validators independently reproduce it**.

Grant review is where "AI on-chain" usually goes wrong: a single model call
becomes a single point of trust. Here the decision itself is what validators
agree on.

- Contract: [`contracts/milestone_reviewer.py`](contracts/milestone_reviewer.py)
- Tests: [`tests/direct/test_milestone_reviewer.py`](tests/direct/test_milestone_reviewer.py)

---

## The problem

Every grants program runs on the same bottleneck: someone has to read links and
judge whether the work matches the criteria. That reviewer is trusted, expensive
and slow, and grantees learn to write for the reviewer instead of for the work.

This contract makes the review a public, reproducible decision:

| Capability | API |
| --- | --- |
| Fetch and render the evidence page | `gl.nondet.web.render(url, mode="html")` |
| Score against written criteria | `gl.nondet.exec_prompt(prompt, response_format="json")` |
| Agree across nodes | `gl.vm.run_nondet_unsafe(leader_fn, validator_fn)` |

---

## Lifecycle

```
open_grant(title, criteria)                 # criteria >= 40 chars, stored verbatim
        |
submit_milestone(grant_id, summary, evidence_url)
        |
        v
    status = "submitted"
        |
        |  anyone calls review_milestone(id)
        |    leader:    render evidence -> prompt(criteria, summary, page)
        |               normalize -> {decision, score, findings, reasoning}
        |    validators: re-run; require decision == leader.decision
        |                and |score - leader.score| <= 15
        v
    status = "reviewed"  ->  stored verdict, score, findings
```

Nobody is privileged at review time: once a milestone is submitted, any address
can trigger the review, and the outcome is decided by the validator set rather
than by the caller.

---

## Normalization

An LLM scoring a grant is the most non-deterministic thing in the pipeline, so
its output is reduced before it leaves the nondet block:

| Field | Type | Validator rule |
| --- | --- | --- |
| `decision` | `pass` \| `partial` \| `fail` | must match exactly |
| `score` | integer 0–100 | within ±15 |
| `findings` | up to 4 short strings | ignored for consensus |
| `reasoning` | one or two sentences | ignored for consensus |

Invalid decisions fall back to `fail`, scores are clamped, and findings are
truncated. The contract never stores an unvalidated raw model response.

## Prompt-injection handling

Grant evidence is untrusted: a submission can include text aimed at the
reviewer. Criteria, summary and page are fenced as data inside the prompt, and
the model is told never to follow instructions found in them.

## GenVM rules this respects

- all `gl.nondet.*` calls live in the nondet block;
- storage is written only after `run_nondet_unsafe` returns an agreed result;
- ids increment inside write methods, so they stay consistent across nodes.

---

## API

| Method | Type | Description |
| --- | --- | --- |
| `open_grant(title, criteria)` | write | Registers a grant, returns its id |
| `submit_milestone(grant_id, summary, evidence_url)` | write | Adds a milestone to review |
| `review_milestone(milestone_id)` | write | Renders evidence, scores, commits verdict |
| `get_grant(grant_id)` | view | Grant record with milestone count |
| `get_milestone(milestone_id)` | view | Milestone record including verdict |
| `total_grants()` / `total_milestones()` | view | Counters |

Guards: title ≥ 6 chars, criteria ≥ 40 chars, summary ≥ 20 chars, `http(s)`
evidence URL, one review per milestone.

## Run the tests

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

pytest -q                       # 10 passed
genvm-lint check contracts/milestone_reviewer.py   # Lint passed (3 checks)
```

Direct mode mocks the page fetch and the LLM, covering creation guards, unknown
ids, the milestone counter, pass and partial reviews, and double-review rejection.

## What it demonstrates

- a second, non-market use case for the same consensus primitives
- a rubric-driven decision (criteria written by a human) rather than a
  free-form question
- partial credit: a numeric score that validators tolerate within ±15 while the
  categorical decision must match exactly
- defensive handling of untrusted submissions
