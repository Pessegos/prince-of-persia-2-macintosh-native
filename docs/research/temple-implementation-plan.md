# Temple implementation plan (proposal, 2026-10-30)

A proposed order for making levels 10-13 playable, written from Codex's
53 temple research notes (`temple-*.md`) and the ruins integration
experience. It is a plan for discussion with Codex and the user, not a
claim about what is done. No production code changed with it.

## What exists

- Inventory and headers (`temple-preparation.md`): levels 10-13 are
  environment 2, opponent set 7 (Temple.rsrc, Birdhead.rsrc, Prince CTBL
  25002), start rooms 22/5/19/3; LEVL 2009-2012.
- Mechanisms with native-checked reference models and fixtures: pressure
  plates and their lifetime/links, gates (admission, standing, contact,
  distance, ejection, hanging, animation, TROB), sliding rocks
  (admission/geometry/contact/motion), floating ceilings, collision banks
  and history/sweep/decision, ground bump, air/armed collision responses,
  Prince frame metadata, controller geometry and PlayerCtrl inside the
  world caller.
- Not present: an exported temple scenery program, a running temple level,
  birdhead opponents, the temple CUST rooms and the story transitions.

## Proposed stages

1. **Scenery export for environment 2.** Extend the slot exporter that
   already renders environments 3/4 (`tools/extract_caverns.py`,
   `tools/extract_slots.py`) to Temple.rsrc: cells, PIEC/SHPL, CUST 4025/
   4075 rooms and palettes, with a slot-oracle check like
   `check_slot_scenery`. Gate: every room of levels 10-13 renders and the
   oracle agrees.
2. **Level loading and walking.** A `Temple` environment (like `Ruins`)
   that loads level 10 at room 22, with the existing terrain, controls and
   saves; mechanisms inert. Gate: walk, jump, climb and fall through all
   reachable rooms without errors (scripted traces), saves round-trip.
3. **Mechanisms from the reference models.** Wire plates, gates, sliding
   rocks and floating ceilings into the world frame in the order of the
   recovered FrameAdv phases, reusing Codex's models as the single
   implementation where they already are production-quality, one family
   per commit with its fixture traces as regressions.
4. **Collision.** The temple's collision banks and responses replace the
   simpler terrain collision only inside environment 2, with the recorded
   native traces as tests.
5. **Birdheads.** Opponent set 7 (Birdhead.rsrc FRAM/AFRM, 108/85 records):
   controller research is still needed; follow the ruins head approach
   (probe each leaf, then integrate).
6. **Story.** NIS 2's last shot (DrawRoomFromNIS(10, 22), horse in plane 1)
   once stage 1 exists, then the level 9 -> 10 transition; the later
   temple scenes and levels 11-13 transitions.

## Division of work

Codex owns the temple mechanism research and its reference models. A
natural split: Claude takes stages 1-2 (exporter, environment, level
loading), which reuse the ruins pipeline Claude built; Codex wires its own
models in stages 3-4. Birdheads (5) and story (6) can be assigned later.
Each stage integrates separately with the usual reservation.
