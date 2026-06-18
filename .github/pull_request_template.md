## PLAN
<!--
- restate the task
- list touched or inspected surfaces
- name the main risk: public boundary, host state, typing/nervous, bootstrap,
  release artifact, GitHub route, or local runtime behavior
-->
- ...

## DIFF
<!--
- say what changed
- say whether installed host behavior changed or only public source/docs changed
- name generated surfaces rebuilt or intentionally left unchanged
-->
- ...

## VERIFY
<!--
- `python scripts/ci_gate.py --mode source-fast` status
- `python scripts/ci_gate.py --mode release-public` or narrower release gate status
- host-contract, typing/nervous, self-awareness, or live checks when touched
- GitHub `Repo Validation` status when landing
- what was not run
-->
- ...

## LIVE HOST EVIDENCE
<!--
- include only public-safe summaries of local host checks
- do not paste live `/var/lib`, `/srv`, secrets, captures, typed text, indexes,
  transcripts, or private logs
-->
- ...

## REPORT
<!--
- current public/runtime contract after the change
- whether publication boundary, branch protection, release artifact policy,
  bootstrap/install projection, or local host behavior changed
- operator follow-up still needed
-->
- ...

## RESIDUAL RISK
<!--
- unverified host assumptions
- freshness warnings
- bootstrap or lifecycle paths not exercised
- GitHub settings or branch protection not checked
-->
- ...
