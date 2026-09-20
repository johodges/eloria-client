# Nymara diagonal-continent QA hibernate checkpoint

Full local resume state, hashes, queue, and the exact dirty-path inventory are in:

`C:\Users\User\Desktop\eloria-project\work-output\diagonal-continent\HIBERNATE-CHECKPOINT-2026-09-20.md`

## Verified

- The active published master is internally consistent: `continent.glb` SHA256 `61cb075e0fd9de34c65bb30b518ed2018d1a220016c5526953321865f1375112` equals the master digest recorded by `publication.json`, `master-scene.json`, and `export.json`.
- `export.json` records the actual active `composition.json` SHA256 `be527a96356c4f60cde78851a1cc91492bf1c98abc3a01c48f9af1fc5d965d1f`.
- The active current-input epoch is composed world `ad6d60b1cfa34bc70d44b5fc287ed538327f4efdb5341babb5fc433a389a203d`, plan `54ddec547568e83ae87fcc568ac2a87ce05317cd824522a5eeeee0b477ccb97a`, object edits `e70917acee8f0788798fb32f2d4443a8e763c24b25d600e564b13abcf3cbfcad`, and composition algorithm `f71b2ae866055f0053c020e8f17e61c9970e22d3c2f01ad78035cb95a15a813c`.
- Commit `5151169372a62564172d42ca3d40b2b9b5d26e31` is a two-file baseline reconciliation only. The current snapshot SHA256 is `387fd9cb52429ee21f3ca5d557966c249f978ef063de98bc7216ccb463f3120b`; all 33 files recorded by that snapshot are present and match their recorded SHA256 digests.
- Root's merge-tree check of cached `origin/develop` `59bb84a7479d2c9f2e06968a5ca91be558fdea36` plus `515116937...` produced tree `03730601f4982248be3b979326d6debfa6bbc941`; the merged diff is exactly the two baseline files and preserves the newer crowd-optimization commits.
- The combined Whitehorn v4 isolated library and composition stages completed. Their cached extraction and change-localization reports are durable; a rebuild is unnecessary for diagnosis.

## Rejected for publication

- Do not publish or merge the generated map set yet. Known Primary support/contact, Whitehorn routing/terrain propagation, Row1 entrance fit, lower seam, upper solid, and remaining bridge coverage issues are unresolved.
- The combined Whitehorn candidate moved the Primary ground target by `+0.150770145 m` and changed 3,864 final F32 terrain vertices. Frozen v10 footing contact results therefore do not certify that candidate.
- Component501 continuous-water v1 timed out before substantive checkpointing and is HOLD. No v1 retry is allowed.

## Pending

- First resume task: a cached Whitehorn stage/operand causal replay. It must identify the first remote-change stage and compare exact Primary foundation and Whitehorn routing operands; no compose or build.
- Re-run no completed producer. All physical acceptance must consume the existing epoch-pinned cache or a separately reviewed successor.
- Before another substantive run, harden the bounded runner so it validates the exact Python/wrapper argv positions and terminates the owned process tree at the remaining deadline.
- Use `after/map-comments-20260919/bridge-diagnosis/HIBERNATE-BRIDGES-2026-09-20-v2.md`; do not rely on the earlier literal `BR` checkpoint.

## Repository safety

- Client HEAD is `13a3c23b941ff2426c08a97f85101df6e59069a1` on `feature/world-navigation`. Fetched remote feature HEAD `b4b245689f63f5d623604d26eac4dd3c885fabbd` is an ancestor; local is 22 commits ahead and 0 behind.
- Server HEAD is `bde0f87aafa4cb95cba2c03b4631d5f7a318a0a6`, equal to fetched `origin/develop`; the server remote has no `feature/world-navigation` ref.
- The first sandboxed fetch attempt failed because SSH port 22 was denied. A subsequent authorized fetch outside the sandbox succeeded for client `develop`, client `feature/world-navigation`, and server `develop`; the ancestry above uses those freshly fetched refs. The recorded local HEAD values are the state before the checkpoint document is committed.
- Keep all generated modifications and unrelated untracked media unstaged. Do not force-push. If the feature ref is no longer a fast-forward after connectivity returns, publish a new checkpoint branch instead.
