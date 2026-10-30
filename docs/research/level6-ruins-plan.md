# Level Six: Ruins Scenery And Integration Plan

Research note, 2026-10-22, updated 2026-10-23, `claude/ai-research`. Level
six is playable from the cliff, without its heads and serpents. Codex's level-seven notes (branch `codex/level7-preparation`) cover the
shared environment-4 dependencies and the head/serpent actors; this note
covers the campaign track: scenery export and runtime integration.

## Identity

LEVL 2005 is level six, environment 4 (Ruins), start room 27 (port 26),
cell 23, opponent set 5 (`Head.rsrc`). Levels six and seven share
`Ruins.rsrc` (CTBL 3500-3502, PIEC 3500, SHAP 3501+, CUST 4025, 4200, 4250,
4275, 4300, 4325, 4350, 4375 and 4650) and the Prince palette CTBL 25004.

## Native Scenery Export (done)

`tools/extract_caverns.py` now draws any environment whose piece table is
decoded (`DRAW_KINDS`):

- The per-environment piece-drawing tables sit at a5-0x4aea + 4 * env. The
  caverns' table has 45 entries (kinds 0-44); the ruins' has 24 (0-23),
  followed by unrelated data.
- The ruins drawers in CODE 7 call SectRect (a5-0x1f58) at `7:1f2e`,
  `7:1f8c`, `7:2760`, `7:2b1a` and UnionRect (a5-0x1f5c) at `7:1f48`,
  `7:1fa2`, like CODE 8's cavern drawers.
- Shape library 0 is the sword item (SHAP 1000 + index, `Prince.rsrc`):
  level six's room 17 (port 16) has a tile-22 sword at cell 15.

With these, all 32 rooms of level six export with the original renderer
under Unicorn; levels three to five export byte for byte as before. A test
render of port room 16 matches the ruins look.

## Known Differences From The Caverns

- Pressure plates and gates use other SHAPs. In levels six and seven a plate
  (kinds 5/6) changes SHAP 3554 to 3555 and also redraws 3552 (kind 5) or
  3553 (kind 6); the exit moves 3547 (caverns: 3566); the gate is 3542
  (caverns: 3562/3563). `tools/extract_pressure_plates.py` and the runtime's
  shape remapping (`pop2/caverns.py`) assume the cavern shapes and need
  per-environment tables or stored variant commands.
- Port room 26 (the start room) is a CUST room (4650, kind 22). Its enter
  hook `7:37a6` (template table a5-0x4c2e) loads CTBL 3502 at entry 64
  (`S03_508A`), covering entries 64-218; with that overlay the exported
  room renders correctly. Its leave hook `7:37b6` restores CTBL 3500 at 64
  under a condition still to read. The shared hook `7:37d6` (kinds 20-22)
  only acts in level nine (rooms 16 and 2).
- The sword item SHAP needs the Prince/sword palette, not CTBL 3500.
- Cavern-only data (torches 3581-3589, lava) are skipped for environment 4.

## Implemented (2026-10-22)

- Import of `Ruins.rsrc`/`Head.rsrc` and `ruins_level6.json` (loose-floor
  variants delta-encoded: 24 MB instead of 115 MB, identical expansion).
- Ruins plates use their exported toggled commands; gates (3542) and exits
  (3547) move like the caverns' with clips 19/10 pixels above the row. All
  plate/gate/exit records of levels six and seven match native redraws.
- Loose floors shake with the column-parity tables a5-0x2c66/-0x2c7e
  (7:2bd6). Each table names two shake images (values 1 and 2); phase 1
  shows one and phase 3 the other in both tables. Since 2026-10-24 the
  export keeps both: a ruins loose cell's choices are rest, phase 1, space
  (and the struck copy) plus phase 3 last, and `cavern_scene_signature`
  picks the second image whenever the phase's value differs from phase 1's.
  All twelve phases of an odd- and an even-column cell compose exactly as
  the original renders them (phase 12's value 98 is never drawn: the
  original's renderer has no shape for it). The ruins exports grew by 0-14%
  (level six 440 -> 501 KB). The caverns' table (8:24dc/257c, two lookups)
  only yields 0/1, a single shake image, so their variant was already
  faithful.
  `tools/check_slot_scenery.py --level 6` (its oracle now renews the
  harness every 400 rooms) compared 41,006 room variants: 123,018 lists,
  all equal to the original renders.
- Level six starts on the cliff (SEQS 2, native X 374) without a sword
  (a5-0x500a = -1, 3:6202); crouching at the sword item (tile 22) takes it
  (6:14ce-1574, SEQS 91, FindSwd 183). Saves keep a changed sword type.
- Finishing level five loads level six; the ruins' exit song is 124.
- Tile predicates (IsSpace/IsWall/IsFloor, CODE 3) are environment
  independent, so the existing collision rules apply.
- Crevices (tile 7) start covered (InitState 3:5dce clears bit 0x80) and a
  crouching or crawling Prince uncovers the first run of the row
  (RuinSetCreviceRevealed 7:3404, scan 7:332a).
- Crawling (2026-10-23): crouched with Down held, forward into a crevice
  whose foreground low bits are not 3, or a scythe (12/13), lies down
  (GenCtrl 6:0a4e-0b28, SEQS 125, X aligned to at most 10 pixels into that
  column facing right, 34 past its right edge facing left). Prone (poses
  246-261, 6:07ee-0994): forward crawls (122), back (123); he stands (124)
  when neither his own, the front nor the rear cell is 7/12/13, or with Up
  once clear of a crevice behind him (6:08a4-0942). A body at most 34 pixels
  high passes an open crevice (CheckCollide 4:5ade-5b0a, heads excepted),
  and the wall alignment skips a prone body in a crevice (4:35e6, 4:5830).
  These rules are environment independent, so level two's two crevices
  (port rooms 9 and 11) can now be crawled too.
- Scythes (2026-10-23, port rooms 18 and 20): tile 13 holds the state and
  AnimScythe (5:4584, in an unmapped listing region) copies its low byte to
  the tile 12 on its left. A living Prince or guard on a scythe cell, at
  most 30 pixels above the floor and more than 28 pixels into the column
  (5:57bc), starts a resting scythe (TriggerScythe 5:5fde). Each update
  advances phases 1-19 (sound 277 leaving 0, 276 leaving 15; from 16 a
  bloody blade also bloodies the handle, 0x80), then returns to 0 keeping
  the blood. CheckScytheHit (5:588a) tests only the first scythe cell among
  the character's columns -1..+1: phases 2, 16 and 17 (GetScytheHitType)
  cut with the rectangles a5-0x372a/-0x3722 offset by the cell (tile 13 one
  column right; guards' right edge inset by 10), except poses 267-271 and SEQS
  44: SEQS 113 and death method 5 for the Prince (SEQS 190 for a guard),
  sound 278 and blood (0x40) on both halves. The drawing of each of the 60
  states is exported as a patch of the native room drawing
  (`tools/extract_scythes.py`); it needs a reimport, and older imports
  leave the scythes still. (The climbing redraw layers came later with the
  slot export; the crawl under a blade uses S05_5F1A's blade state.)

- Flip flask (2026-10-23, kind 4, level six's only one): DoPickupEffect
  4:4672 calls 2:59f6, which turns the world for 1080 updates (a5-0x4fa8,
  song 176) or rights it (song 177). FrameAdv 2:67ba-67d6 counts down while
  the Prince lives and rights it at 1. Poison drunk upside down only rights
  it (4:4678-4682). GenCtrl swaps Up and Down (4:3da6-3dcc, 4:3e1c) and the
  game area is drawn upside down (2:5952-59de). The state survives restarts
  and the change to level seven. Not reproduced: a level-seven checkpoint
  stores it as 0 (2:1744-1766) and checkpoint rebirth restores it (2:19b4).

## Level Seven (2026-10-23)

Level seven (LEVL 2006) now opens after level six, with the same ruins
export (`ruins_level7.json`, 1.3 MB) and still without heads or serpents.
CheckPlayNIS(6, 7) may show a tree scene first. Its entrance depends on how
level six was left: the next-level opcode -16 (4:2f3e-2f56) stores 2 in
a5-0x500c when the Prince's column is >= 6 (level six's right door in native
room 16 ends at column 6, the left one at 2). SetKidDefaults 2:5eda then
starts in native room 4, cell 25, and shuts room 32's door; otherwise room
32, cell 24, with room 4's door shut. The export draws the upper door's
closing frames (`alternate_entry`); its loose-floor variants are not
combined with them. Saves keep the entrance. Levels seven and eight start
with sword type 2 (3:61ec). Level seven's own site 5:09a0/0a74/0b68 is in
the exported drawing.

## Levels Eight And Nine (2026-10-24)

Both use environment 4 with Ruins.rsrc and open after level seven: LEVL
2007 starts in native room 16 and 2008 in room 10, both with the ordinary
standing entry (SetKidDefaults 2:5e34, SEQS 5). Levels seven and eight
continue through CheckPlayNIS (tree scenes); level nine stops before NIS 2
and the temple. Their exports (`ruins_level8/9.json`) need a reimport.
Level nine's room 16 has two scythes read by one slot; the slot export now
stores tables that never change once, which keeps it small. Heads and
serpents are still not generated (`docs/research/ruins-head-leaves.md`).

## Crevice Reveal Drawing And Crawling (2026-10-24)

User report: an uncovered crevice showed the wrong wall art. RuinSetCrevice
Revealed (7:3404 -> 7:332a -> 7:344a) sets bit 0x80 on the run and, for each
cell it uncovers, MarkRedraw (5:18f0 via 5:1936) if IsVisibleRoomCell
(5:3960: the room itself, or column 9 of the left room, mapped -9), plus
the cell right of a run end (low bits 0, column < 9). RedrawCell (3:1d3a)
then repaints only those cells, with the full-room flag a5-0x4832 clear,
over the displayed screen: the wall above the tunnel stays. The harness has
this per-cell mode (`cell_redraw`); the slot export stores each crevice
run's redraw (`redraws`), drawn over the covered run until the room is
entered again, when the whole room is redrawn natively (with the revealed
backdrop). Older exports keep the whole-room drawing; reimport needed.

Crawling: the port's rules match the original's code. A prone body passes
any crevice whose low bits are not 3, covered or not (CheckCollide 4:5ade:
shape height a5-0x3560 <= 34); lying down (GenCtrl 6:0a4e-0b28) first moves
a left-facing Prince to at least 34 pixels right of the crevice's column.
From there SEQS 125's frame 259 (35 pixels high, so still a wall) reaches
the barrier GetRightBarr = column x + 22 + 50 when the Prince had walked
flush against the crack (a repeated bump, SEQS 47); from one step back
(standing left edge >= 104 in native room 18) he lies down and crawls
through. Whether the original also bumps from flush is unverified in play.

Resolved (2026-10-24, `tools/probe_crawl_lie_down.py`): the original runs
CheckBarr 4:4e34, CheckCollide1 4:54da and Collide on those frames. Facing
left at X 85, frame 259 (35 pixels high) enters the crevice's barrier and
collides; but Collide's unarmed branch 4:59b6-59dc treats a prone pose
(246-261) specially: AddCharX(-5) and SEQS 121 (lying still), not the
standing bump 47. The port chose 47, so the Prince stood up and, with Down
still held, lay down again in a loop: the tunnel bug. Now the prone bump
backs off 5 and stays down; the left-facing lie-down reaches X 89 in SEQS
121 and crawls on, matching the original. The cell tests of the crawl
(GetCellsInFront 4:39fc, 4:35a6, 4:3a48) now read the stored column
a5-0x504a, i.e. the supporting foot's column, as the original does. A sweep
of every open crevice run of levels two and six to nine from both sides
found no remaining loop except a run closed by a crevice whose low bits are
3 (impassable by design).

## Done Since (2026-10-24)

- Heads and serpents run in play: `docs/research/ruins-head-leaves.md`
  (controllers, combat, neck alignment, wall contact, saves, native probes).
- Room ambient: PlayAmbient 5:4fd0 with the ruins' bank (LEVL 0x2186 = 4:
  groups 139-154 and 155-170, combat 171-174) and the room table at 0x424a;
  OppToFight 6:2392 counts an angry or fleeing head (-0x5024 > 0), never a
  serpent.
- Sword type 2 (levels seven and eight, and the sword found in level six's
  sword type): LoadSwordSet 3:5a4e draws SHPL 1200 with Kid AFRM 25201
  (3:5aae-5ab6, 5b2a-5b3e); other types keep SHPL 1000 and AFRM 25001.
- The start room's leave hook 7:37b6 restores CTBL 3500 at 64 only while the
  Prince is alive (-0x50b6 < 0) and a5-0x4fce is set; the port picks the
  palette per drawn room (`ROOM_PALETTES`), which gives the same result on
  leaving.

- Level nine's CUST kinds 20 (native room 2) and 21 (room 16) share the
  enter hook 7:37d6 (template table a5-0x4c2e: kinds 20/21 -> 7:37d6, kind 22
  -> 7:37a6/37b6). Entering room 16 with the Prince's column >= 9 adds song
  292 (Chasm); entering room 2 with his column < 5 adds song 185 (Horse) once
  (a5-0x4ff8). The heads' InjrHead 136 and KillHead 137 are songs (AddSong),
  not sounds. These songs and the flip flask's 176/177 are now rendered by
  the audio import (`RUINS_SONGS`); an older import has no files for them
  and stays silent until the game is imported again.

- Level eight's throne room (native room 9, CUST kind 34). The enter hook
  7:3864 loads Ruins CTBL 3501 at 48 (`ROOM_PALETTES`) and, until the vision
  is over (a5-0x4ff4), adds Throne1 (180) with the Prince's column < 9, or
  SeeThron (179) once (a5-0x4ff6). The first crouch at the sword item there
  (6:14d6-152a: room 9 of level eight, item kind 22) moves him AddCharX(-23)
  and, facing left, AddCharX(4), starts SEQS 237 and adds Throne2 (181); the
  item stays. At SEQS 237 pose 185 in that room, 4:3dd0 calls 7:38ca:
  PlayNIS(6), then facing right, SEQS 231 on the floor, life restored
  (pending = maximum), the father's sword (a5-0x500a = 1), a5-0x4ff4 = 1,
  the level redrawn from a saved copy, and Throne4 (182, queued when a song
  plays). Afterwards the sword is an ordinary item without FindSwd (183,
  skipped in that room by 6:1554-1568). The flags are optional save
  fields. Throne songs are rendered by the audio import (`RUINS_SONGS`)
  after a reimport.

## Cutscene 6: The Vision At The Throne (2026-10-25)

Follow-up validation (Codex): SpecialMusic 5:5388/5418 selects Throne1 even
without combat, until sword type 1; ordinary room ambience resumes after the
vision's foreground music. GetBarrCode 4:52bc/532e selects type 8 for the
level-eight throne gate, with DATA offsets 16/24, independently of its phase.
`tools/probe_throne_room_rules.py` executes 128 music and 128 barrier cases
with controlled LEVL/room/sword/combat fields and no supplied services.
`tests/test_throne_room.py` covers playback repetition, both collision planes,
cautious clearance and the real scene's return to ordinary ruins ambience.

PlayNIS(6) from 7:38ca reaches NISThroneRoom 15:66f4 (dispatcher 15:07c8,
table entry 6). The import runs it like the other scenes
(`tools/extract_intro.py`, `recover_throne`, `throne.json`) and the port
plays it with the scene player before waking the Prince
(`ScenePrototype.start_vision`, `Ruins.wake_from_vision`).

- Files: ThroneNIS.rsrc (A5 file record -0x26aa; SHAP 32001-32005, CTBL
  32001) at id offset 600000, and the game's own open files, searched after
  NIS: Ruins (400000), Kid (700000) and Prince (800000).
- Order: ShowNthvRGB 17:130e sets entries 1 and 2 to (255, 90, 0) and
  (255, 181, 0); 15:6e24 loads Kid CTBL 25004 (at 16) and Prince CTBL 1004
  (at 240) and combines them (RemapCTBL 17:6a78, CombineCtabs 17:1520);
  CTBL 32001 replaces 48-229; SHAP 32001 (the restored palace, 510 x 365)
  with DrawDeadKid 15:6c66 on top: Kid SHAP 25081 at the Prince's X - 221
  (mirrored by FreeShpInfo 17:5fd0 and 21 further left when he faces right)
  and Y - 19, and the sword (Prince SHAP 1011) at (271, 345). The scene
  waits for Throne2 (game song 181, MIDISnd 9933) to end, starts its own
  music (NISMIDI 31020) and shows the picture. Correction: although the
  previous scene frees its dissolve data, NIS(6)'s common prologue
  15:006a-0072 calls InitDissolve(1), preparing the whole 512 x 365 picture
  before 15:66f4. The exporter now includes that setup; the first dissolve
  runs for its original 240 ticks rather than taking the no-data copy path.
- The apparition: InitDissolve(2) limits later dissolves to the rectangle
  at a5-0x22fc (77 x 104) moved to (X - 214, or 39 less facing right; 210).
  SaveRect 17:520a keeps the background there; SHAP 32002-32005 fade in
  over it (180, then 20 ticks each) after music cue 97.
- The words: TEXT 32000 lines 1, 2, 3, 4, 6 and 8, each with its voice
  (NISDIGI 32001-32004, 32006, 32008); lines 5 and 7 are never shown. While
  the scene runs (a5-0x27dc), NISTextDraw 15:026e-028c uses the strip saved
  at a5-0x27da (the picture's top 87 lines) as the panel and colours 1 and
  2 instead of SHAP 25002 and 3/14.
- The end: after music 31020 the scene starts Throne4 (182, MIDISnd 9934),
  dissolves the apparition away, redraws the ruined throne room
  (QueenAddNIS 15:6d46, environment 4: Ruins SHAP 4200-4207 and the
  Prince), fades out all colours and fades the room palette in (Ruins CTBL
  3501), restarts Throne4 if it has ended (SoundIdOn 16:25b0) and leaves it
  playing. 7:39d4 then only queues 182 while it plays; the port's queue
  skips a playing song.
- Two variants (native facing 0 and -1) are exported against the reference
  position (474, 346) (X with the 207 origin; Y row 2's floor). Drawing at
  DrawDeadKid 6cc4 follows the Prince's X and Y, the apparition's SaveRect,
  dissolve area and shapes his X (`follow`).
- Port approximations: the screen before the scene is the game's last
  frame on the Macintosh; the port draws the scene's own room redraw there
  (with Ruins CTBL 3500/3501 and the combined Kid/Prince colours). The actual
  game HUD below line 365 is retained as RGB through the scene, so palette
  changes cannot recolour unrelated palace pixels as status graphics.
  Standalone previews without a game HUD use black there. An area dissolve uses
  its own shuffled pixel order, not LoadSaveDisRes 15:3878. Skipping the
  scene wakes the Prince and lets the game start Throne4.
- Checks: all existing scene programs (intro, voyage, discovery, carpet,
  nine trees) are unchanged by the harness additions; MoveRect 17:1b4e now
  moves the rectangle to the point (17:1b12) instead of offsetting it,
  which those scenes did not distinguish.

Follow-up visual fixes (Codex): resident Kid SHAP inks 1-16 are mapped to
16-31 (zero remains transparent); NIS text uses its saved strip's actual
rectangle at the top, leaving the picture and HUD below untouched. Mother's
180/20-tick dissolves, dialogue/music cue timing and total scene duration
are unchanged in both facings. The static scenery exporter now supplies the
view room for DrawSword 3:4cf2 and the unowned-item projection (-0x500a=-1)
for 3:4d56-4d60, not an uninitialized weapon value zero. This draws the intact
father's sword without an ordinary floor patch over the custom throne floor;
runtime weapon ownership is unchanged. A local old/new native command audit
of all 224 base rooms in levels 3-9 changes only level 8 room 9.

## Level Nine's Horse (2026-10-30)

Native room 2 of level nine (port room 1) shows the rearing horse on its
pedestal. DoCleanCut (2:608e-60b2) sets a5-0x4832 while it draws the room;
the back plane of the drawing list (3:23e4-2418) then asks
GetHorsePtInPlane (3:4584-459a: plane 0, room 2, level 9 -> a5-0x4af6 =
(40, 252)) and DrawHorse (3:4608) adds Prince SHAP 25360 at x 252, y 40,
masked (flags 16) and mirrored in level nine (3:46a0-46b6 -> FreeShpInfo
1). Its colours are Prince CTBL 25360, loaded at entry 1 for that room
(3:1004-1022). The slot export does not contain it (the exporter draws the
cells, not the drawing list's horse object);  adds it
after the back pieces. Planes 1 of level 14's room 1 and level 10's room
22 (a5-0x4aee/-0x4af2, while a5-0x5000 = -1) are the later horse scenes
and are not drawn.

## Remaining Steps

1. The retained cliff image when walking left from the start needs a visual
   comparison with the original game (playtesting).
2. Level nine's exit leads to the temple (NIS 2 and level ten), which the
   port does not support yet.

The scythes' climbing redraw layers, listed here earlier, are covered by
the slot export (schema 2): every room's `climb_source`/`climb_141` lists
are composed per slot state, scythe slots included (for example level six
room 16 and level seven room 3).

Cutscene 1 between levels five and six is now implemented; see
`level5-native-rules.md`, "Cutscene 1: NISCarpet", including the unresolved
music-cue continuity. Updated installations need the new scene resources.

## Scythe jumping contact correction (2026-10-26)

The room19 running-jump report exposed two contact errors and a death-pose
alignment omission. Trigger5:57bc and CheckScytheHit5:588a read the cached
supporting-foot column A5-504a, refreshed by LoadFrame4:2a72 via
GetFCharX4:3a72/GetCharCol4:3ad6. They do not recompute the column from the
sprite anchor. Using the anchor could miss the first half or select the wrong
half farther along, both allowing contact escapes and cutting beyond the blade.
Both host queries now receive the actor's current frame record. The first
scythe cell still owns the decision, including inactive phases; this is not a
blanket rule that every jump through an extended trap must die.

ComputeBladeHitRect5:5a1c uses the original DATA rectangles. The guard inset
at5:5910 subtracts10 from RIGHT, not BOTTOM. After a hit,5:596e immediately
executes AnimChar: original SEQS113/190 both start with -7,5,-19, then their
first pose267/241. That -19 calls SetCharFloor4:31fa, placing ordinary actors
at106+120*row. The host cut handler now applies that alignment and stops its
free-fall motion; a jumping victim no longer leaves a suspended corpse.

`tools/probe_ruins_scythe_contact.py` executes the original trigger/contact
predicates with real ReadCell, hit-type selection, blade-rectangle instructions
and DATA. Local report: `rendered/ruins-new/native-scythe-contact.json`;
8,580 contacts,864 trigger admissions and6 independent SetCharFloor calls,
zero mismatches. The corrected fixture is LEVL2005 (header level6), with
room19 cells25/26 explicitly asserted as12/13:3,471 contacts and334 trigger
admissions are positive. The initial LEVL2006 report accidentally used level7
walls and exercised no positive contacts; that report is invalid. The probe
now rejects a wrong level, absent scythe or all-negative/all-positive results.
It also checks original cut-sequence prefixes. QuickDraw
UnionRect/SectRect/OffsetRect and their stack cleanup are supplied; actor
snapshots, inclusive body rectangles and supporting columns are fixtures.
The type2 fixtures reuse Kid frame offsets to vary the supplied column, not
to claim Guard FRAM parity. Actor and level bytes are checked unchanged by
the predicate queries. Contact stops before death/audio/blood-write endpoints;
trigger stops before TriggerScythe. This excludes full FrameAdv timing,
body-edge generation, trap capacity, rasterization, room crossings and
whole-game equivalence. Imported-scene regressions cover a missed jumping
contact, a false contact beyond the blade, delayed foot activation and the
corpse's floor alignment; an asset-free regression covers the guard inset.
