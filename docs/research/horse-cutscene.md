# Level-nine horse transition repair (2026-11-04)

Scope: the upper-column leap, NIS 2 and the first playable room after the
ride. Temple mechanisms and later levels are outside this repair. The user's
`Macintosh Horse cutscene.mp4` and `Port Horse cutscene.mp4` show the same
intended route, with different initial positions and input timing.

## Findings and changes

The existing CutChar trigger works in the supplied port recording. Native
`6:4a68-4ad6` requires facing left, drawn left <=191 (scene -16), level9,
native room8 (port7), row0, pose41. Its caller supplies the drawn bounds and
current actor state. It increments a5-0x4f92 instead of cutting into native
room2. NIS 2 supplies the fall onto the horse. Preserve this trigger; an
additional collision trigger on the horse's floor would change the route.
The new integration regression runs the actual jump and actual scene player,
then enters level10 room22, without substituting a fake scene callback.

The desert shot's long empty hold was an importer error. `NISTemple 15:615e`
calls PlayTheAnimation for ANI25012, with TransFunc5. `15:654a-6552` returns -1
when the music marker a5-0x1f6e >=97; this permits **early termination**.
Independently, runScript opcode0 clears the animation's running word
(`16:099a-09a4`), and PlayTheAnimation tests isRunning at `16:14c4-14d0`
(`16:078a-0796`). The caller proceeds on a normal script end. There is no
subsequent WaitMusicCue(97). The previous exporter inserted one anyway.

Remove that synthetic cue. Existing `kind: temple` imports are normalized
on read by removing only cue97 with source PC0x615e; genuine cues elsewhere
and other scene programs are preserved. Fresh exports and normalized old
exports were compared: the same 5,037 operations, exactly. No resource or
audio reimport is needed. The local nominal scene duration falls from
43.6996s to34.4653s, removing9.2343s of empty scenery. This is the portable
player's nominal clock, not a measurement of Macintosh event-loop stalls.

The moving desert layers also reached the HUD strip, leaving fragments of
rocks visible underneath later shots. The initial unused right edge could
turn white when palette entry1 changed. For NIS2, initialize the offscreen
to black index255, constrain shape drawing to the510x365 picture and retain
a black status strip. SetGameRect `17:1ada-1af4` supplies width510; the game's
picture is365 rows and the recorded NIS has a black HUD area. Other scene
programs retain their existing drawing bounds and status behavior. This is
presentation containment; it does not certify native dirty-rectangle unions
or rasterization.

The red horse at the end of NIS2 disappeared on the first gameplay frame
because only level9's statue was drawn. GetHorsePtInPlane `3:45a0-45e8`
returns a5-0x4af2 for level10, room22, plane1 when a5-0x5000=-1: top-left
(74,198). DrawHorse `3:468a-46d2` uses Prince SHAP25360, masked, unmirrored
outside level9. Palette selection `3:1058-1076` loads Prince CTBL25361 at1.
The back/front drawing-list admission is `3:23e4-2414`. Draw this statue in
the arrival room's front layer, including its global actor mask. It remains
visible after the dismount and in front of a Prince who walks back behind it.
NIS2's animated last shot continues to use its own exported horse frames.

## Independent original-code check

Run from the worktree root, using a read-only sibling recovery directory:

```powershell
.venv\Scripts\python.exe -m tools.probe_horse_scene --source ..\PoP2-Mac-Code-Recovery --output rendered\horse-native.json
```

`tools.probe_horse_scene` executes original CODE16 runScript `08ee-0ada`
against all five original TempleNIS SCRPs, comparing layer IDs, positions,
flags, intervals, sound events and running state to the portable decoder.
There are338 incremental calls, including five terminators, with no
mismatches. This is independent execution of the decoder's source rules;
the port's decoder is the comparison target, not the native implementation.

| ANI | Displayed frames | Nominal ticks | Running after terminator |
| --- | ---: | ---: | --- |
|25011|64|384|false|
|25012|76|456|false|
|25013|46|276|false|
|25014|94|564|false|
|25015|53|318|false|

Sixteen original TransFunc5 calls cover frames0/1/76/77 and music markers
0/96/97/98: returns0 before97 and -1 from97, independently of frame. One
original GetHorsePtInPlane call confirms the arrival point. The level9 and
level10 fixture headers are checked against original LEVL2008/2009.

Supplied endpoints: constructed animation objects, handles and vtables;
HLock/HUnlock no-ops; virtual sound/notify methods record commands; TransFunc5
flip, copy and palette calls are inert sinks; callback frame/music globals;
arrival plane1 and global -1. No native drawing, synthesis, Resource Manager,
maintain/event-loop timing, full PlayTheAnimation or FrameAdv replay runs in
this probe. The earlier-music-marker abort is checked as a native callback
rule, but the portable export still follows the finite script under ordinary
imported music timing.

## Regression and visual verification

`tests.test_horse_scene` checks old-import compatibility, the desert-to-canyon
cut, every frame's black margins, statue continuity and front occlusion, and
the full jump/scene/level10 handoff. On unchanged08264a4, four methods reject
the old behavior (442 failing subcases); the route integration method already
passes, confirming that this report did not require replacing CutChar.

The recordings were inspected as frame sheets and the portable scene rendered
offscreen before/after. The final statue's visible pixels match Prince
SHAP25360/CTBL25361 in the scene and the playable room (accounting for the
game viewport's one-pixel room origin). No live game/emulator, physical input,
user settings/save changes, original-resource writes or release build.

Full shared-desktop discovery in a worktree-local Python3.10 environment:
3,411 tests, OK, ten explicit exclusive-desktop skips (680.2s). Fresh-import
GUI cancellation and completion both pass. Dependencies, Ruff F/E9, recovery
catalogue and whitespace checks pass. The preliminary focused command had
one misspelled module name (`test_throne_scene` instead of `test_throne_room`);
full discovery includes the correctly named module. The local report retains
ordinary Tk theme-destruction messages and Pillow deprecation warnings; no
test failures. Publication commit is recorded in the local handoff.

Remaining limits: no complete audio waveform/timing or native pixel parity
claim; later temple work remains deferred.

## Follow-up: continuous leap, music and doorway (2026-11-04)

The user requested three further adjustments after ca72756, and supplied a
marked still of the distant temple entrance. These are presentation choices;
they do not change the recovered CutChar trigger or claim native equivalence.

The first leap still paid for `IntroAssets('temple.json')` on the gameplay
thread, then waited another gameplay tick and any current effect through
`LevelExit(None, 0)`. One local cold preparation measured 196ms for assets
and 8ms for the initial player, excluding rendering and effect completion.
Prepare/cache NIS2 assets while binding level9 instead. On the horse trigger
tick, stop the remaining gameplay phases and enter/render NIS2 immediately.
The user explicitly requested removal of the initial delay, so this bypasses
the native current-effect wait at `2:6134-6168`. Other level exits retain
their gates. No per-frame animation intervals are shortened.

There are two different songs. Native `7:37d6-3836` requests game song292
(`Chasm.mmf`) on entering level9/native room16 with column >=9. NIS2's
`TransFunc6 15:6580-6596` starts scene song25006 (`ToTempl2.mmf`) at frame2
of ANI25013, while the chasm is still empty. The first follow-up3092b9d
misinterpreted the request and moved Chasm into the scene. The user corrected
that interpretation, heard an18s ToTempl2 preview and explicitly approved it.

The current port keeps both gameplay hooks: Chasm292/room16 and the
Horse185/room2 one-shot. It delays the original ToTempl2/scene25006 until
the actual takeoff pose: ANI25013 frame34, Horse SHAP25333 (exported725333),
at17.257598s. Frames1-29 are the empty establishing view, and frames30-33
the approach. The earlier riding theme keeps its existing ending and is
not restarted. Scene audio uses its existing banked metadata/WAV, with no
game-song metadata dependency, resource reimport or new synthesis.

For ANI25014, the marked entrance's inner right edge is picture x362. Apply
a temporary drawing clip with right362 for this shot, leaving its saved
background untouched. The horse disappears progressively behind that jamb,
including the Prince and tail, rather than drawing across the facade.
Restore the 510x365 picture clip before the next shot so the arrival/dismount
and red statue remain intact. The original ANI header's rectangle is
`(top231,left0,bottom365,right365)`; the requested x362 alignment is a port
presentation decision, not an independently recovered native raster bound.

All adjustments occur when reading a `kind: temple` program. Both an older
temple.json and a fresh export therefore receive them without changing the
preserved extraction data or requiring resource reimport. Tower, carpet,
throne and tree programs do not receive these adjustments.

Regression checks exercise the real running jump with a current effect
that reports busy, forbid asset construction during the leap, follow the
ride into level10, check all46 canyon frames for the music trigger, and
compare all94 distant-entry frames against the saved backdrop past x362.
They also require intermediate visibility followed by complete occlusion.
The room-entry regression asserts the native Horse185 and Chasm292 requests;
the cutscene regression requires scene25006 exactly once at takeoff and
rejects game292 throughout the ride. The scene's nominal duration remains
34.465319s. A second local timing sample
measured228ms of preparation moved to loading and7ms for a prepared player;
these samples exclude rendering and are not a hardware-wide latency claim.
Offscreen frame sheets confirm the marked jamb and gradual disappearance.
The user reviewed the before/after GIF and explicitly approved this entrance.

For easier playtesting, the user also requested the upper platform when
choosing level9's Room8 in the development menu. Give the existing safe-entry
selector preferred row0 only for level9/port room7. The selected floor is
column3 (x183), facing left. A regression idles there without falling, and the
real ride integration test now starts from this actual menu entry. Campaign
entry data and ordinary movement/physics rules are unchanged.

The first follow-up3092b9d passed82 focused tests and full shared-desktop
Python3.10 discovery3413 tests in642.705s, with ten explicit exclusive-desktop
skips. Its current-effect-wait and scheduling changes remain unchanged by
the subsequent music correction and development-menu entry preference.
The correction passes222 focused horse/arrival/ruins/development-entry/menu/
cliff/audio/carpet/throne tests, no skips (39.067s), plus dependencies, Ruff
F/E9, catalogue and whitespace checks. Its three changed regressions reject
3092b9d (16 failing cases, no errors). An AudioEngine recording sink resolves
ToTempl2 to `scene-0-25006` on the music bus at17.257598s, with no292 request
in the cutscene; the complete scene still lasts34.465319s. Full discovery was
not repeated for these audio-presentation and development-menu changes.
No live user game/emulator, focus/input, user saves/settings, source-resource
writes, source-assets import or release build was used.
