# Level Four And The Story Clock

## Scene Selection

The supplied Macintosh transition capture agrees with original selector
`2:0180-027e`: leaving level 3 selects NIS 10 (Discovery). It does not start
the countdown. The first restart of level 4, or reaching level 5 without a
level-four death, selects scene 20 and sets the tree stage from -1 to 0.
Later restarts do not repeat that first tree scene or reset time.

`pop2/story_progress.py` translates this selection after the existing
load/copy-protection admission. Specific level transitions take priority over
the timed tree check. The original tree stage advances only when the new
stage exceeds the previously shown one, using `7 - trunc((minutes - 1)/9)`.
Following the first tree scene, the positive-minute thresholds are 63, 54,
45, 36, 27, 18 and 9. The timeout sequence is a separate original path.

The countdown prefix at `2:51f4-5270` requires a nonnegative tree stage, a
native-alive Prince and positive minutes. It decrements the frame counter;
on zero it reloads 719 and decrements minutes. This is an eligible original
simulation update, not a repaint or a wall-clock second. Native host cadence
must be respected when connecting it to live gameplay.

The pure model passes 3,024 original selector comparisons and 192 original
countdown-prefix cases, with no differences. The selector fixture supplies
copy-protection success and bypasses queued-load admission. The clock probe
stops before HUD work. These checks establish the rules, not the complete
runtime transition, saves, cutscene playback or timer presentation.

## Level Data And Scenery

LEVL 2003 identifies level 4 as cavern environment 3, starting in native
room 1, tile 25, row 2, port X=277, decoded facing 0. The entry dispatch
`2:5d98-5e36` reaches the ordinary sequence-5 branch for a fresh level-four
start. The importer now prepares independent scenery programs from LEVL
2002 and 2003, including all 32 rooms, entrance closure, torches, loose-floor
variants, climbing/floor redraw and pressure-plate bindings. The renderer and
developer-map drawing select the appropriate program for each level. The
approved wall retouches are scoped by level and room. Level-four room12 now
also has the user-approved local shadow continuation described in
[`CAVERN_ARTWORK.md`](CAVERN_ARTWORK.md); shared native shapes are unchanged.

Export version 15 initializes room links through original `3:1ab0` before
the cell passes. Without this setup, DrawCaveFloorCommon `8:1998` misses an
upper-room loose floor beneath the first-row decoration in level-four room
19 (563 pixels). This also corrects room-link-dependent loose-floor variants
in level 3; existing base scenery and approved retouches are unchanged.

The native whole-room audit passes all 32 level-four rooms and 80 directed
room cuts after that correction. It compares static transfer commands and
layer replay, excluding actors, animated torches/lava, flask rectangles and
HUD. It shares the SHAP decoder and is not an independent Macintosh
rasterizer or a complete dynamic-gameplay test.

## Playtest Entry

Level 4 is now selectable in F3's level/map tools, using the fresh ordinary
sequence-5 entry. Its menu/map expose the 28 connected rooms; unlinked
scenery-only rooms 8, 30, 31 and 32 remain in the export/audit, not in the
teleport list. A bounded original `2:5d98-5e36` dispatch execution confirms
sequence 5 with no extra animation frames for both levels 3 and 4; it stops
before JumpSeq and is not a full initializer comparison. Existing cavern
controllers handle the entrance door, mechanisms, skeletons and ambience.
Host tests cover entrance settlement, a room-19 warp, restart, a save preview
and progress load back at the level-four entrance. Snapshot loading uses
level-four lava tables rather than borrowing level-three room records.

This is a level-four playtest, not a complete later campaign. The level-three
completion now plays Discovery and enters level four, retaining maximum life.
Tree playback, live countdown, story-state persistence and onward progression
are not yet connected.

Discovery uses NIS.rsrc's original 29000-range resources. The tree scenes
also require NISTree.rsrc, which was not needed by the opening/voyage importer.
Their ANI/SCRP playback and callbacks must be recovered along with drawing,
voices, MIDI markers and palette changes. A fixed captured video is not the
source of the port's scenes.

The bounded Discovery coordinator probe now reaches its end with the three
animation bodies supplied as successful returns, preserving 142 coordinator
operations/call markers. Original call sites `15:237c`, `15:23f6`, `15:2456`
use base 29000, ANI/SCRP 1/2/3, flags 6, position (63, 61), and no callback.
This does not execute PlayTheAnimation or establish playback timing.

The last script includes a sound-control command for 29100. Original
KBAnimation soundControl `16:0f34-0f52` starts it in sound bank 1, while the
coordinator also uses 29100 in MIDI bank 0. Both resources actually exist.
Discovery audio is now imported under bank-qualified `scene-kind-id` keys
and filenames, separate from legacy gameplay/opening cues. IntroPlayer resolves
both formats; the audio engine passes both bank entries to SDL. The same ID
can therefore play on the music and effect channels without overwriting either
file, duration or MIDI markers. The launcher checks both sets of files.

## Discovery Playback

The importer now executes the original Discovery coordinator, expands its
three callback-free ANI/SCRP calls into portable drawing/sound/wait operations,
and writes `discovery.json`. No Macintosh CPU or captured video runs during
gameplay. Only PlayTheAnimation flags 6 with zero background fill and no
callback are admitted here; other callback/restore modes fail explicitly.
ANI header position is replaced by SetPos, not added to it. The shape bank
starts at base+1 and layer shape N resolves to base+N. Layers draw in ascending
order over the persistent target; their rectangles are copied to the display.
Sound command zero is ignored, as in KBAnimation soundControl `16:0f42`.

A fresh local probe executes original runScript `16:08ee`, SetPos `16:0538`
and draw `16:01f8` with carried state. All 69 displayed frames and 144 draw
calls agree on order, coordinates, flags, interval and nonzero sound events.
The probe supplies OffsetRect/division, memory locks, RTD adaptation and shape
dimensions; callbacks are recorded and shape rasterization is not original.
It does not execute the full PlayTheAnimation event loop or real audio.
The earlier independent runScript probe also covers 12 Discovery/tree scripts
and 481 incremental steps, without differences; this is not tree callback
or timing certification. Native maintain `16:0454-0464` schedules from the
current tick; portable playback uses the nominal resource intervals and the
existing deadline-based cutscene host, not Macintosh stall/catch-up parity.

Host regressions cover level-three completion, automatic arrival in level
four, health retention, pause, skip-key suppression, F3 seeking and isolated
gallery previews. F3 exposes the new sequence under After Level 3. Fresh
imports stage the scene and all audio before replacing installed files.
Existing installs need reimport; the new scene/audio files are not bundled.

Before playback, GetEndSong `5:4e0c` selects cue 32 for cavern environment 3,
just as for rooftops. AddEndSong `5:4b40` requests it, and FrameAdv
`2:6134-6168` waits for the song/effect gates before admitting the transition.
The port reuses its existing LevelExit gate; the frozen room remains visible
until the cue ends, then Discovery starts once. Silent playback uses the
imported cue duration. This does not implement every exceptional native
effect exclusion or the Macintosh window/fade pipeline.

## Tree Scenes

PlayNIS `2:0308-0322` maps public scenes 20 or above to NIS `scene - 8`, and
the NIS dispatcher `15:0102` calls TreeCheck `15:0568` with `NIS - 11`. Tree
scenes 20..27 are therefore variants 1..8. Variant 9 (NIS 20) is the
separate timeout path.

The importer runs TreeCheck for each variant with the same CODE 15 harness
as Discovery. It overlays NISTree.rsrc (SHAP/CTBL/ANI/SCRP) on NIS.rsrc
(TEXT 26000 and the border remain there) and rejects any ID collision.
- **Variant selection:** the palette is CTBL `26000 + (v + 2) / 3`, through
  the runtime division `19:4bb0`, which the harness reproduces; the music is
  MIDI `26010 + v`.
- **Callback timing:** PlayTheAnimation `16:13d4-13f8` draws a frame and
  calls the callback with the displayed frame number before copying it
  (`16:140a`). TreeFunc `15:04d0` acts only for frame 2.
- **Callback expansion:** its operations are recovered separately, by
  running `15:04d0` with argument 2 and a5-0x245c set to the variant. They
  are inserted between frame 2's drawing and its copy:
  - all variants: the fade-in;
  - variant 1: captions 1 and 2 with voices 26001, 26002 and 26004, a
    60-tick timer, and caption 3 with voice 26005;
  - variant 9: waits on MIDI markers a, b and c, then CTBL 26028.
- **Calls treated as no-ops:**
  - SetSHAPColors `17:0a52` prepares an offscreen colour table that indexed
    drawing does not use [I];
  - the port save/restore calls `17:3260`/`17:322e`.

The importer writes `tree-1.json` ... `tree-9.json` and installs
NISTree.rsrc. The launcher requires them, so existing installations need a
reimport. A fresh import of the reference HFS image reproduced every other
prepared file byte for byte.

## Story Clock At Run Time

RestartGame `2:5b66` calls CheckPlayNIS for every restart, and its loop
(`2:5c7e-5cc2`) re-enters it whenever FrameAdv returns the same level after a
death. The host therefore asks `StoryProgress.select_scene(level, level)` in
`restart_level` from level four onwards and plays the selected tree variant
over the restarted level. The first restart plays variant 1 and starts the
clock; later restarts play a variant only when a minute threshold raises the
stage. Discovery on 3->4 still does not start it.

KeepTime `2:51f4` runs once per FrameAdv for a native-alive Prince. The host
advances the clock once per gameplay step:
- not during cutscenes, pause, copy protection, the door entry or level
  completion;
- frozen while the Prince is dead.

At zero, FrameAdv calls TimeUp `2:7194`: PlayNIS 28 (tree variant 9), the
tree stage back to -1, and FrameAdv returns -1, which ends RestartGame's loop
(`2:5c86`). The host plays variant 9 and then starts a new game.

**Persistence:**
- the clock and tree stage are campaign state on GameSession;
- level loads carry them over and New Game resets them;
- progress saves store them in an optional `story` field, omitted for an
  untouched campaign. Older saves without it still load.

**Time messages.** KeepTime requests a message:
- when a minute below five or a multiple of five begins;
- in the last minute, every twelfth update, replacing the message on screen.

It formats "%d Minutes Left", "%d Seconds Left" with `(frames + 1) / 12`,
"1 Second Left" or "Time has expired!" from the A5 strings `0x558c-0x55aa`.
The text is shown for 24 steps and erased at 1 (FrameAdv `2:67e8`, `6834`);
FirstFrame clears it at each level start. The host draws it in the HUD line
with the existing interface font. The native DrawMessage `3:4252` shadow
colours are not reproduced.

**Leaving level four.** GetEndSong selects cue 32 for environment 3, as
when leaving level three. After the song, CheckPlayNIS(4, 5) runs, so a
player who never restarted level four sees the first tree scene now. The
completed level then stays on screen, because level five is not available.

Level five (LEVL 2004) also enters with sequence 5 (`2:5e34`).

**Level-five scenery (research step).** The export harness now produces
`caverns_level5.json`:
- **OffsetRect:** it services every OffsetRect trap in CODE 3/5/8, which
  covers bridge floors (OffsetBrgFloorY `8:07fe`, RestoreBrgFloorY `8:085a`)
  and custom pieces (`3:120a`).
- **Custom rooms:** rooms 3 and 10 are customized (foreground bits 0xc000,
  IsCustomizedRoom `3:1310`). For those, the harness locks CUST
  room*25+3975 at a5-0x4c9e (LoadCustomRoomData `3:1378`) and runs
  DrawCustomRoomImgs `3:2324` natively. It records each DrawCustomRoomImg
  `3:2438` call as an item of the requested pass (back for 0/5/11, front
  otherwise) with the SectRect clip (`3:2482`).
- **Result:** room 10's rope bridge and room 3's custom chamber render.
  Back pass 11 now runs for CUST rooms (`3:1d24-1d2e`); it draws room 3's
  ceiling bars, whose phases follow the room's plate (see
  `docs/research/level5-native-rules.md`). Existing installations need a
  reimport to see them.

The export of levels 3 and 4 is byte-identical to before.

**Level five as a playtest level.** Level five can now be played, much as
level four was at first:
- the importer writes `caverns_level5.json` and the launcher requires it, so
  existing installations need a reimport;
- F3 lists level five, and saves accept it;
- after the exit song and any first tree scene, the level-four exit loads
  level five, keeping the maximum life.

**The rope bridge breaks** (`pop2/bridge.py`, CODE 8). The Caverns frame
hook (A5 table -0x46f8, entry `8:3b92`) calls BridgeCheckBreak after the
characters move, in level five's rooms 7, 10 and 12:
- **Counter:** while the Prince and the room's first opponent stand on
  bridge tiles (44) within three columns, a5-0x3132 rises each frame;
  apart it falls by one, and with fewer than two on the bridge by two. The
  Prince standing (frame 15) or in frame 185 does not count (`8:01f6`).
- **Break:** at 60, with the Prince in columns 4-6, the opponent in 5-6 and
  the Prince's selected sequence not 85, the state goes 1, 2, 3; then one
  plank per frame drops, from column 7 down to 3 (sound 123 and song 121 on
  the first). Each emptied cell becomes tile 0 with foreground 0xc000, so
  the characters fall. The state ends at -1 (earlier if the Prince's
  selected sequence is 85); a Prince in column <= 4 facing right then
  moves 17 pixels (AddCharX).
- **Planks:** each dropped plank is a mob (`8:0c1a`): Rnd(1) makes it hang
  (frames 0-7, held at 7) or fall (frames 8-13, then removed). Tables
  a5-0x3188/-0x316c/-0x3150 give its CUST record (SHAP 4226-4232) and draw
  offsets; DrawObjBrgFloor draws it at the column and the row-1 floor plus
  the column's sag (a5-0x319a: 2, 4, 6, 7, 7, 7, 6, 3).
- **Scenery:** a native redraw of each collapse stage equals the room-10
  export without the fallen columns' SHAP 4226 commands (also the climb
  layers), so the port filters them.
- **Turns:** DoTurn (`6:26c0-26d8`) and the voluntary turn
  (`6:2314-2330`) are refused in room 10 while the state is positive.
- **Creak:** sound 122 at Rnd(40) with both characters on the bridge,
  Rnd(80) with one, unless it is still playing (`8:0534`).
- **Sag:** on a bridge tile, outside frames 34-44, the native Y follows the
  plank sag (`8:063e`); the port applies it to drawing only.

- **Falling opponent:** IsBrgGateOpen (`8:035e-0392`) removes an opponent
  that falls out of the bottom of rooms 7, 10 or 12 (RemoveChar), so the
  skeleton is not carried into room 11. Like other off-room opponents, one
  that is still falling when the Prince leaves room 10 waits there.

Not reproduced: the per-plank wobble (`8:06d8`, RedrawBrgFloor) and the
±1 Y it adds; the opponent AI bridge predicates (`8:02ae`, `8:04a2`) and
IsBrgGateOpen's other branches. The other level-five rules are listed in
`docs/research/level5-native-rules.md`.

**The level-five finale (room 3).** The upper-right plate toggles the
ceiling bars. Crouching on the carpet sits the Prince on it and the carpet
rises; with the bars open it carries him out of the level (SEQS 128 ends
with the next-level opcode), with them closed it crashes into them and he
dies (death method 9). Details and the provisional carpet palette are in
`docs/research/level5-native-rules.md`.

**Relief sigh (sound 110).** When a gate slams shut (the fast close of a
reversible plate, ATMGate `5:4290-42ce`, not squashing anyone), `5:4766`
checks: level 4, not already used; the gate is in the Prince's room and row,
fewer than five columns from him; and every living opponent in that row is
on the gate's far side (at least one). Then a countdown a5-0x5008 = 4 runs in
FrameAdv (`2:640c-6446`); at zero a living Prince outside modes 3/4 plays
sound 110 and the countdown becomes -2, so it happens once per level. In
practice this is room 24's gate shutting out the chasing skeletons. The
disassembly listing left `5:4198-4681` and `5:4752-48af` unmapped; they were
read with capstone.

**Not yet implemented:**
- the death message's 600-frame game-over timeout (`2:67fa-6806`).
