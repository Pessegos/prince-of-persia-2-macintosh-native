# November ruins playtest corrections

The supplied Macintosh/port head-tile and serpent-impact recordings accompany
ten user reports. Room numbers below are native, one-based. The fixes use the
Macintosh resources; the requested tunnel stopping behavior is a deliberate
port improvement. The approved horse cutscene, audio, artwork and README
wording are unchanged.

| Report | Cause and resulting behavior |
| --- | --- |
| Level7 room5->9 falling-tile head trick | The loaded-actor contact path existed, but the unloaded-record path did not. Falling tiles now crush the downstairs head while the Prince remains upstairs. Flight speed is unchanged; the recording alone does not establish a separate speed defect. |
| Level7 room28 head in the left room | The native screen-entry transfer was omitted. Room20's near-edge head record moves into room28 on entry, with rebased X47. |
| Serpent hitsplash | SetupHit3:0bec-0c0e selects Head shape127, body-anchor X-12 and Y+7, retaining Kid palette16 from3:0bc2-0bc4. The port used Kid burst218 and ordinary guard offsets. Both facings now use the serpent effect and its correct palette. |
| Empty map rooms | Hide level8 rooms27/15/7 and level9 rooms23/22 from F3's map. Traversal confirms these are exactly the removed rooms. Native LEVL data and gameplay links stay intact. |
| Level8 room2 tunnel endpoint | Preview the crawl's first translated SEQS/FRAM body against the actual barrier, including the native five-pixel prone backoff. A blocked hold stays at prone pose251; reversing still works. This is the user-requested improvement over the original's repeated preparation poses. |
| Tiles on opener buttons, level8 room17 | Ordinary kind5 impacts selected timed opening2 instead of permanent opening3. The impacted plate keeps timer31; the gate reaches255 and stays there, including an impact on an already open gate. Reversible plates retain their existing behavior. |
| Sword after level8 room9 vision | Corrected after the user's two follow-up videos: the floor sword stays after the vision, and Ctrl still draws the old sword. Physical pickup consumes the item and loads the father's sword art. The first batch's floor-consumption shortcut was incorrect and is superseded below. |
| Level8 completion | The ordinary completion-opcode host stopped its supported-level list at7. It now creates the level8 exit gate and reaches the existing 8->9 story/level loader. |
| Level9 room12 serpent | The same omitted screen-entry transfer: room13's X815 record moves left into room12 at scene X98. Death and record identity persist across room changes. |
| Level7 room8 scythe freeze | Rubble adds low-byte bit0x20, absent from exported animation/blood states. Mask that decoration bit when selecting a rendered state. Let the dynamic scythe foreground override the stale rubble impact phase so the trap also completes its full cycle. |

## Native room-record evidence

`tools.probe_ruins_room_records` executes original CODE against original
LEVL2005..2008 and asserts each level header and opponent set5. No supplied
service endpoints are used. The harness supplies current/left/right room
globals from the actual links, and debris X/Y/velocity for contact calls.

- CheckSideRoomsForVisibleOpps6:2f4e-308a, called at6:2b82 before the room's
  InitOpps loop, traverses left then right. Native X>585 on the left and
  X<331 on the right qualify, strictly. It copies the38-byte record, adds
  -510/+510 to X, appends through AddOppToRoom6:358e and removes the source
  through6:3462. Source/destination slots are updated. The comparison checks
  every resulting native room-record tuple and the production host's loaded
  room memberships, X, row, kind and skill:110 entries,11 transferred records,
  zero mismatches. Full-destination native loss is excluded; the port retains
  its capacity safeguard.
- MakeRubble5:3576-3640 chooses loaded contact when the debris room matches
  the loaded bank, otherwise ContactOppInfo5:377e-3812 and
  CrushOppInfo6:29fa. The record contact uses row-floor minus57, except set5
  kind8 serpents which use the floor itself. It requires
  `0 < debris_Y - threshold <= 4 * velocity`, with the same debris column.
  This is distinct from the loaded head's FRAM/height predicate.
- Record columns use signed long division19:4bb0 of native X-229, truncating
  toward zero. GetCharCol5:48b0 is not interchangeable at negative X; the
  independent probe rejected that first implementation at level7 room22's
  offscreen head. The corrected production helper matches6,720 contacts,
  including784 positives and explicit threshold/velocity/column negatives.
- Offscreen heads are removed from their room records, rather than given a
  sword-hit death. Serpents keep flattened SEQS169. Loaded-actor slab deaths
  continue through the separately recovered146/169 path.

The probe excludes full FrameAdv, elapsed-video timing, drawing and complete
AI equivalence. SetupHit's serpent branch is read from original CODE3 and
pixel-checked against original Head shape127 in both facings; this is not an
independent raster-decoder comparison. No emulator window or original files
are modified.

## Reproductions and validation

`tests.test_ruins_bug_reports` reproduces the ten reports in hidden, isolated
scenes. It exercises the real level8 completion callback; all scythe phases
after an actual falling-floor impact; a350-tick gate wait after a room17
impact; floor-item reentry; room transfers and serpent death retention; held
crawl input and reverse input; and the upper/lower room slab contact.

The slab regression drives the actual Down/Shift descent and Up climb from
room5. The head moves under its real controller, ending in the lower
platform's column3; no head X/timer is supplied. It then forces the later
room5 cell23 collapse and verifies the offscreen contact and return-room
result. It does not claim a frame-exact replay of all user inputs in the
video. The corrected room/record paths explain the observed failure without
an arbitrary head speed adjustment. An asset-free regression also rejects
the incorrect negative-X column formula and unbounded debris contact.

Local native report and visual comparisons are under `rendered/ruins-bugs/`.
The focused ruins/mechanism/combat/map/input run passed343 tests, no skips.
Final full-suite and integration results are recorded in the session handoff.

## Serpent palette follow-up

The user's comparison stills revealed that the first shape127 correction used
Head CTBL750 to colour its pixels. SetupHit changes the library to3 but keeps
the common effect's palette base16; that palette belongs to the Prince, whose
SetKidPalette3:5f1c loads Kid CTBL25000+environment at16. In ruins CTBL25004,
shape127's central ink7 is RGB220/141/70 (orange), instead of Head CTBL750's
168/46/117 (pink/purple). The corrected effect decodes with the already loaded
Kid palette; silhouette, positioning, timing and the serpent body stay the same.

A bounded original CODE run executes3:0ba4 through the branch to3:0cc6,
including real4:4972 and4:2bda. Supplied inputs are body draw point300/200,
both facings, actor type11, poses252..289 and a prior palette base32. All76
calls produce library3, shape127, palette16, the facing-relative12-pixel
offset and Y207. No services are stubbed; AddObj/rasterization/full scheduling
are excluded. Local evidence: `rendered/ruins-bugs/native-serpent-hit-palette.json`.
The strengthened both-facing pixel regression rejects6b8fe08 and checks the
actual orange colour rather than deriving its expectation from the Head palette.

## Father's sword pickup follow-up

The supplied `macintosh dad sword behaviour.mp4` shows the floor sword still
present after the vision, Ctrl drawing the old short sword, and the father
sword becoming visible only after physical pickup. The port video instead
switched the displayed sword immediately. Removing the floor item at wake,
as the first batch did, misunderstood the report; that change is removed.

The missing distinction is native cached artwork, not the logical sword word:

- Post-vision7:391c-395c selects wake sequence231, restores life, marks the
  vision complete and sets logical sword word A5-0x500a to1. It does not call
  LoadSwordSet. The loaded sword type at A5-0x46da remains2, so SHPL1200 and
  Kid AFRM25201 still supply the short sword. The floor item stays type22.
- Physical pickup6:152c-1552 selects91, consumes the cell, sets the logical
  word from the item and explicitly calls LoadSwordSet3:5a4e. The loader
  replaces the cached type with1, selects SHPL1000/AFRM25001 and loads the
  sword palette. Checkpoint/exit/music/damage logic continues to read the
  separate native logical word; the existing recovered gates remain intact.
- `ScenePrototype.loaded_sword_type` now carries that runtime art cache.
  Level bind, normal restart and checkpoint restart reload from the logical
  word; physical item pickup updates it explicitly. It is not a new saved
  field. Room changes preserve the loaded art, as they already preserve the
  floor item's consumed/unconsumed state.

`tools.probe_throne_sword_loading` executes original7:391c up to395c and
6:152c up to1554, including real LoadSwordSet3:5a4e, LoadKidAttachFrames3:5b2a
and LoadShapeSet3:5e7e. Four traces (both input facings, low/full life) agree:
after wake logical1/loaded2/item untouched; after pickup logical1/loaded1,
with resource requests AFRM25001, SHPL1000 and CTBL1004 at240. Supplied
endpoints are the already loaded working Prince, JumpSeq and ChangeCell
effects, synthetic resource handles, resource-file/memory traps, GetResource,
LoadShapeList and PoPSetPalette. It excludes PlayNIS, actual sequence/cell
effects, the resource manager, rasterization and full FrameAdv equivalence.

The regression drives wake completion and Ctrl with the floor item present,
then ordinary held-Shift crouch/pickup, subsequent room reentry and fresh
restart. A checkpoint regression checks art reload and the uncollected item.
The inspected offscreen comparison is
`rendered/ruins-bugs/throne-sword-sequence.png`; native trace output is
`rendered/ruins-bugs/native-throne-sword-loading.json`.
