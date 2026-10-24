# Temple Actor-To-Plate Lifetime

Research only, based on `31b5bdf`. Connects native CheckPress5:127e-13dc
to ordinary PushPlate5:240c, permanent pressure5:252e-2552, real rock-only
link activation and the previously recovered plate TROB release/compaction.
This does not enable the temple or alter game runtime behavior.

## Boundaries

The five original, header-admitted rock-only sources are level10 room28
cell24, level11 room29 cell4, level12 room1 cell21, and level13 rooms5/16
cells18/17. The raw level12 room29 source remains excluded by its header.
The two mixed gate/rock sources are not in this connected release probe:
their target gate animation needs a separate reference model.

Supporting column/row, actor bytes, FRAM auxiliary word, floating flag and
the order of CheckPress versus animation calls are supplied. Six plans cover
tap/release/re-press, held pressure followed by FRAM rejection, actor/mode/Y/
selected-sequence exclusions, above-cell pressure, permanent pressure, and
the type4/nonnegative-ALIVE exception. Above-cell controls may place the
supplied supporting row outside the visible room; these are branch fixtures,
not assertions of reachable player poses.

Audio5:4d84 and redraw5:0f38 are request sinks. Loose-floor5:2710 and
trapdoor7:36a0 remain guarded request sinks too, but neither is reached by
these five-source native traces. A synthetic unit test pins that exclusion.

## Findings

- Real admission may leave the cell cache on the above cell or on a linked
  rock. Rejected actors must not accidentally reuse that cache to refresh a
  plate. The full ordered read list/cache and persistent banks are compared.
- Ordinary admitted pressure creates/refreshes the plate's existing lifetime
  before linked rock activation. Releasing pressure does not reverse rock
  control; five release calls lift an ordinary fresh plate in this supplied
  call schedule, not necessarily five rendered frames.
- Permanent pressure writes timer31 **before** calling PushPlate, with
  explicit `(cached kind, foreground low-byte index)` arguments. It therefore
  skips fresh source registration, sound and redraw while still activating
  the linked rock and setting the depressed bit. Subsequent living pressure
  leaves that permanent timer intact in the tested trace.
- Kind4 with ALIVE0 takes ordinary pressure instead, including source TROB
  registration and release. ALIVE and displayed dead pose are not synonyms.
- A full TROB bank can reject source registration without rejecting the
  linked rock activation. If those slots later disappear, held pressure alone
  need not recreate the missing source record while timer5 remains stored.

No complete FrameAdv order, supporting-foot computation, rock movement,
target gate animation, actual sound/pixels, save/reset or final-level
playability is claimed.

## Evidence

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_actor_plate_lifetime --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_actor_plate_lifetime_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_actor_plate_lifetime_reference
```

540 persistent traces:2,520 native CheckPress operations and4,590 native
animation operations, **7,110 comparisons with zero mismatches**. The probe
observes1,620 PushPlate entries (including90 from the permanent wrapper),
90 permanent entries and900 rejected checks with no pressure endpoint.
It records345 audio requests and525 redraw requests, not sound or pixels.

Each operation checks the complete level bytes, live/unused MOB and TROB
storage, scratch records, object/rock calls, redraw/sound events, ordered
pressure calls and arguments, OS scratch, press flag, all ReadCell requests
and the six-word cache. Current/saved62-byte actor canaries and another
unchanged global are checked separately. The instruction whitelist and
fresh-call stop guard reject unexpected native execution.

Ten asset-free regressions cover ordering, stale-cache rejection, permanent
versus type4 pressure, above-cell admission, capacity and the inclusive Y
boundary. The executable is
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`;
compared-output digest is
`f6b6ac621e56c12a10ce95071e834be1b593fef7cfce27f989c337f27df6a498`.
All four LEVL hashes remain in the ignored report.

Next: independently bound the permanent wrapper over all admitted plate
sources, then recover target gate animation and connect mixed chains.
