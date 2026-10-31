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
- Stage 1 done: the importer exports levels 10-13 (Temple.rsrc is a
  required import file). Level 13's room 4 CUST 4075 draws SHAP 4077-4091,
  which only Kid.rsrc holds (the Resource Manager chain); the exporter now
  receives (Temple.rsrc, Kid.rsrc) for temple levels and marks those images
  library 5. The runtime colours them with Kid CTBL 4077 (stored at
  224-239) by ink order: the blue flame. That colour mapping and the flame's
  animation (pass 11 records 2-16) are hypotheses / not ported.
- Stage 2: a `Temple` environment (levels 10-13) ends levels 10-12 through
  CheckPlayNIS/RestartGame like the ruins and stops after level 13 (NIS 3
  and level 14 are not ported); saves accept levels 1-13. Every temple level
  loads and walks (scripted test). The level menu still lists 1-9.
- Stage 3, sliding rocks (`pop2/slide_rocks.py`): Codex's trigger, motion,
  band-scan and crush-admission rules as production code, checked against
  his references (`tests/test_slide_rocks.py`, 400 trigger and 600 motion
  randomized cases, zero differences). A plate chain reaching tile 25 calls
  TriggerSlideRock (mode 5 resumes, else starts); the Temple environment
  updates the bank every frame (MakeRubble's type 6 case), checks
  CheckSlideRockCrush 10:16f6 and applies 10:1b04 to the Prince (pushed to
  the face; pinned against a wall: pose 185 at control 100, else SEQS 71;
  in the open 93/47/48). The rocks are drawn with DrawMob 10:1788's pieces
  (type 6 3593, 7 3584, 8 3589+phase, 9 3585+phase) clipped to
  ComputeMobRect's rectangle (a filled upper band: heights 109/111) and
  saved. Not yet: the a5-0x3570 width correction (taken as 0), the actor
  events 5:3cee and 6:1a84 (a hanging Prince letting go), rocks drawn from
  a neighbouring room, the gap redraw, Collide's rock edge (93) and
  DoKidEngarde's GetSlideRockX, guards. Level ten's room 28 rock moves and
  crushes a Prince waiting at the wall (scripted test).
- Stage 3, trap doors (`pop2/trapdoors.py`, Codex's 10:25aa/24fa/225c
  rules): ShakeEm 5:28c8 and a landing (Falling 6:0210) open a tile 26
  (space, foreground 0x81 at once; phase 1 under the actor's column, else
  75); MakeRubble advances low phases to 17, ATMTrapDoor draws the
  animation piece (DATA a5-0x2866/-0x2842) and past 16 restores tile 26
  (foreground low byte cleared, cue 27). Saved. Not yet: loop cue 198
  (PrinceSndOn arbitration), the opened cell's static-floor redraw (the
  exported room keeps the closed floor under the panel), neighbour rooms.
- DrawObjLoose 3:4168: falling temple floors draw pieces 28/29.
- Stage 5, birdheads (first part): opponent set 7's initial records spawn
  as ordinary type-2 opponents (6:2bca: raw 7 -> actor 2; raw 1/3/9/10 ->
  10/6/12/0 are skipped, so level 12's raw-1 SEQS 105 actor is missing),
  drawn from Birdhead.rsrc (now imported). Its SHAP 751 is LZ-packed
  (flag 0x0400): `unpack_shape_lz` follows UnpackLZ 17:3aa8 (LZSS, 1,024
  ring from 958). The AI is the ordinary guard's (no Birdhead-specific
  controller found yet); set-7 generation points (0x3986) create them
  too (GenerateOpponent 6:3be0, DATA a5-0x5280[7] = 2). A level-ten birdhead engages and kills an idle Prince.
- Level menu: at the user's request (2026-10-31) the F3/tools level list
  shows levels 10-13 when their scenery is imported; the packaged smoke test
  renders levels 1-13. The temple is still incomplete (see the open items).
- Trap doors, gaps closed: the exporter adds tile-26 cells as two-state slot
  units (closed, or space with foreground 0x81 as TriggerTrapDoor leaves
  it), so an opening door's cell is redrawn without its floor and the
  closed drawing returns with tile 26 (a reimport is needed). The loop cue
  198 follows 10:24fa (requested while a door remains and neither 197 nor
  198 plays) and 10:2328 (stopped when a door closes, then cue 27).
- Stage 3, rock gaps closed: the crush admission adds the saved ShapeBounds
  width a5-0x3570 (copied at 2:6454/4:23ae from 4:5d20-5d56, image width + 1
  plus the sword extension) when the Prince faces left (native -1); a rock
  stopping at spikes runs 5:3cee (spike bloodied 0xf0, Prince impaled in his
  own column, SEQS 54/51, cue 281, death method 4); a rock reaching the
  hanging Prince runs the release helper 6:1a84. Rocks in neighbouring rooms
  draw with ComputeMobRect's projection (5:3364/3380 both pass -510, so a
  right-hand neighbour stays off screen; -365 above, +365 below); that the
  drawing position follows the rectangle is an assumption. The gap's
  MarkMobRedraw rectangle is not needed (the port repaints whole frames).
  Collide 4:589e's armed bump asks GetSlideRockX (10:20fe: right edge X+279,
  left of it 10:180e's left edge, clipped at a wall/gate cell): X below it
  selects SEQS 93 and disarms. DoKidEngarde 6:1fba-2070/20ce-20f2 measures
  the draw from a rock within one column (|edge - X| - GetDist - 6) and
  refuses with the rock behind (`tools/probe_kid_engarde.py` rock sweep).
- Stage 4, collision: `tools/audit_temple_collision.py` runs Codex's
  CheckBarr/CheckCollide1 references for two frames against the port's
  wall correction in every temple room/row (X 10-500 step 7, steps +/-1/4/9,
  both facings, armed and unarmed, empty MOB bank): 371,592 clean starts,
  0 differences. The 113,212 differences all start already inside a
  barrier, where the native finds no new contact and the port's deliberate
  recovery still stops inward motion. Two rules were needed for that: the
  temple's gates take the ruins' type-1 barrier and 4:5b0e admission, and
  tile 43 (IsWall, level 13 only) has no barrier (GetBarrCode 0). Rock
  overlays in CheckBarr (nonempty MOB bank) remain unrecovered.
