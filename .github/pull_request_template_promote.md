## Promote stage → main (Sprint C #3)

Use after `develop` stage Jenkins is green.

```bash
bash scripts/promote_stage_to_main.sh           # dry-run: pins + body
bash scripts/promote_stage_to_main.sh --execute # merge locally
bash scripts/promote_stage_to_main.sh --execute --push
```

Or open this PR `develop` → `main` with title containing `[ci prod]`.

## Summary
- Promote develop tip: `REPLACE_SHA`
- Submodule pins: paste from promote dry-run

## Test plan
- [ ] Stage build green on develop
- [ ] After merge: prod controller runs `[ci prod]` (or Scan Now)
- [ ] `deploy/compose/.last_good_sha` updated on prod host
