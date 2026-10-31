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

## Progress (2026-10-30, Claude)

- Stage 1, mostly done: the native scenery exporter draws environment 2.
  The temple drawers call trap glue the caverns/ruins never reached:
  EmptyRect (a5-0x1f60), UnionRect (a5-0x1f5c) and SectRect (a5-0x1f58),
  supplied as small Pascal routines, and EqualRect (A8A6) in EncloseRect
  17:6c58. Every room of levels 10-12 exports, and level 13 except native
  room 4, whose CUST image is Kid.rsrc SHAP 4077 (the exporter searches only
  the environment file). Exports for caverns and ruins are unchanged
  (compared room by room). Plates/gates/exit shapes for the pressure export:
  gate 3576, exit 3583, plates 3541/3543 and 3542/3544.
- Stage 2 groundwork: with `temple_levelN.json` and Temple.rsrc installed,
  level ten loads and the Prince walks through the rooms (native scenery,
  SetKidDefaults 2:5dee-5e0e: room 22, X 430, SEQS 2). Not done: the
  importer does not export temple levels yet (level 13 room 4 first), the
  level menu lists 1-9, level nine still ends after the ride, and the
  mechanisms, temple gate collision, birdheads and Prince palette 25002 are
  not wired. Do not expose this to players before those.

## Division of work

Codex owns the temple mechanism research and its reference models. A
natural split: Claude takes stages 1-2 (exporter, environment, level
loading), which reuse the ruins pipeline Claude built; Codex wires its own
models in stages 3-4. Birdheads (5) and story (6) can be assigned later.
Each stage integrates separately with the usual reservation.

## Progress (2026-10-31, Claude)

- Stage 6, first part: the ride's last shot is imported. NISTemple's
  DrawRoomFromNIS(10, 22) is played by drawing the exported room's scenery
  as palette indices (`caverns.room_indices`) with Temple CTBL 3500 at 64
  (2:047c-048a); TransFunc8 15:65d4 then animates the horse and the Prince.
  The Prince's shapes come from the resident Kid.rsrc (now a temple scene
  file at offset 900000), mirrored by FlipKids 15:047a(1, 40) and FlipKid
  15:66bc(1); SetKidPalette(2) puts Kid CTBL 25002 at 16; frames 43-46 load
  the statue palettes 25362/25361. Frame 1 copies the game rectangle
  a5-0x4fec into the animation's copy (15:6630); the port shows the room at
  once. After the scene level ten starts in room 22 (SetKidDefaults
  2:5dee) when its scenery is installed, otherwise the game stops after the
  ride as before. A reimport is needed for the new `temple.json`.
