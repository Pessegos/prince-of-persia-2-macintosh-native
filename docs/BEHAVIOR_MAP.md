# Original Behavior Map

The Macintosh executable is the reference. Recovery currently means extracted
resources plus recursive 68k disassembly, not recovered high-level source.
The assembly files contain unmapped ranges and indirect calls. A decoded
branch does not prove that all its callers, state dependencies and ordering
have been recovered. No subsystem below claims complete game-wide parity.

References are CODE resource numbers and offsets in the preserved executable,
under `../PoP2-Mac-Code-Recovery/code/`. Native rooms are one-based; prototype
room indices are zero-based. Exact data, recovered logic and approximations
must remain explicitly distinguished.

## Ownership And Coverage

| Subsystem | Original reference | Prototype owner | Current coverage | Important gaps |
| --- | --- | --- | --- | --- |
| Poses, offsets and animation chains | FRAM, AFRM, SHAP, SEQS resources | `pop2/sequence_runtime.py`, `pop2/animation_data.py`, sprite loaders | Original data and the interpreter operations used by tested paths | Unsupported operations fail; row-changing operations and callers are not a complete terrain engine |
| Keyboard priority and action transitions | ReadKeyboard 2:55d2; GenCtrl 6:0c32, 1014, 11e4, 074a; ClearControls 4:3e3a; sword controls 6:27e8 | `pop2/mac_input.py`, `pop2/control_mapping.py`, `pop2/scene_prototype.py` | Tested locomotion, bounded host buffer, legal transition poses, pose-44 input reset, held-input repetition, native run-stop gates and short/long sheath | Full native per-direction input latches/reset sites, special actors and environmental actions missing |
| Frame cadence | ResetFrameVars 2:68c8 | `pop2/scene_prototype.py` | Five Macintosh ticks unarmed, six armed; deadlines avoid callback rounding drift | Timing is not a substitute for recovering the correct pose/branch list |
| Level coordinates and lookup | LEVL; SetCharFloor 4:31fa; GetCharCol/GetRow; GetFCharX 4:3a72 | `pop2/terrain.py` | Original links, tile words, native column conversion and supporting feet | Dynamic tiles and special-level semantics missing |
| Step clearance, warnings and sword preparation | GetBarrDistances 4:5eae; DoStepFwd 6:1276; draw/turn 6:2072, 26dc | `pop2/terrain.py`, input dispatch in `pop2/scene_prototype.py` | Ordinary floor/gap/wall subset, caution sequence, supported draw/turn offsets | Gate openness, special barriers and full wall-distance branches missing |
| Falls, gravity and landings | CheckFloor 4:35ba; wall correction 4:3982; preparation 4:4b16; StartFall 4:4cbe; Falling/HitFloor 6:00a6/0280 | `pop2/terrain.py` | Supporting feet, ordinary per-pose wall correction, original player/NPC fall sequences and landing thresholds | Full collision buffers and ceiling collision missing |
| Ledge descend, catch and climb | StairClimbing 6:0ece; DoJumpUp 6:1610; Catch 4:37ca; GenCtrl 6:18e0; SEQS 68/24/15/25/210/10/235 | `pop2/terrain.py`, `pop2/scene_prototype.py` | Real rooftop edge checks, native row changes, grip delay, wall-supported stationary hold, free-air expiry and Up-only climb priority | Special levels, blocked climb destinations and complete native clipping missing |
| Viewport transitions | CutChar 6:4918, 4a26, 4dac | `pop2/terrain.py` | Supported facing-dependent bounds, exclusive right edge, pose/state exclusions, neighbor entry check and downward priority | Sword-expanded bounds and full vertical cut timing missing |
| Enemy profiles and generation | LEVL initial/reinforcement records; DATA skill tables; CheckOppGenPts CODE:6 | `pop2/enemy_profiles.py`, `pop2/opponent_generation.py`, `pop2/combat.py`, `assets/enemy_profiles.json` | Extracted profiles/generators; visited-room state; incoming pursuers included in generator corridor checks before ownership transfer | Special enemy controllers and world-wide inactive-room simulation missing |
| Enemy decisions and command gates | EnGarde/OpponentClose/Defence/Strike 4:098c/111a/1204/12c6; AutoCtrl 4:057c/0834; DoRunJump 6:1c14 | `pop2/combat.py` | Ordinary decisions, native profiles, rooftop gap jumps, visited horizontal pursuit and supported alternate-row drop | Full alert/terrain branches, special wider-gap exceptions, other vertical pursuit and all CutOpponent branches missing |
| Damage and parry | CheckParry CODE:6 5978; CheckStab 50ec/523e/53f8 | `pop2/combat.py`, scene recovery handling | Tested range/pose checks, simultaneous-hit priority, unarmed recovery and vulnerable-sequence lethal contact | Special attacks, enemies and environmental deaths need recovery |
| Guard body contact | FrameAdv 2:6c64-6daa | `pop2/combat.py`, `pop2/scene_prototype.py` | Ordinary unarmed bump, actor-type exclusion, native response/distance gates; port jump sweep prevents missed between-frame contact | Jump sweep is a port safeguard; special enemies and exact full-frame ordering missing |
| Pause and Windows presentation | NFNT:23331; native 512x384 viewport | `pop2/game_ui.py`, `pop2/scene_prototype.py` | Escape pause / any key or click resume, Alt+Enter restore, nearest-neighbor aspect-fit, in-game F2 overlay with route-ordered screen entries and peaceful mode | Development selection is level-1 only; menu is port QoL, not recovered Mac gameplay |
| Health display | DrawKidMeter/DrawOppMeter 3:4902/4a8e; low-life flash 2:5442-546c | `pop2/combat_art.py` | Original bottle assets and one-life blink on simulation-frame parity | Upgrade/level-completion meter effects missing |
| Scenery and actor drawing | DrawRoofBackWall/DrawRoofFloor/DrawRoofLedgeInBack CODE:23; ledge-overlap predicate 23:0614; ClipChar 4:4146 | `pop2/render_opening.py`, `pop2/scene_prototype.py` | Original room pieces/palettes; row-owned masks, native 17-22-pixel ledge strips, Prince mode/pose overlap exception and body anchors | Mask-based layering is a subset, not all native conditional draw/clip passes |
| Window escape | Main CODE:2 5d56; CODE:23 roof glass; SEQS/SHAP/DATA tables | `pop2/opening_animation.py` | Isolated recovered opening and original curtain/glass timelines | Intro, opening audio and subsequent scripted scenes missing |

## Boundaries To Preserve

- Input chooses an action at its legal controller transition. It must not
  arbitrarily overwrite a pose halfway through a protected movement.
- Buffering is conditional: native ClearControls discards directional requests.
  Running-jump pose 44 resets them before the next held-key read. The host
  single-command buffer is not a literal implementation of all native latches.
  [INPUT_RECOVERY.md](INPUT_RECOVERY.md) records the reset/priority audit and
  known executable mismatches; expected-failure tests do not certify parity.
- Pose data moves the actor; terrain validates support and geometry. The
  renderer must not silently change position to hide a physics bug.
- Sprite bounds in Pillow are inclusive. Native QuickDraw right/bottom edges
  are exclusive. Convert at the boundary instead of changing every caller.
- A room cut rebases coordinates once and retains action/velocity. An actor
  arriving through one edge must not immediately be cut back by the wrong
  facing-dependent bound.
- Update player floor/room state before enemy control reads it. Not being a
  valid combat target must not disable an incoming NPC's braking controller.
- A guard looping its run poses at a clamped X is not a valid stopped state.
  A controller transition must finish the brake and reach its standing pose.
- Foreground occlusion and physical wall contact are different operations.
  Pixel assertions and position assertions are both needed at the roof edge.
- An ordinary wall-supported hold enters SEQS:25 once; its mode-6 guard
  permits 92/93/93/92/92/91 before -23 holds 91. Test the settling sequence
  as well as the stable pose. Left-facing gates retain their separate branch.
- Normal floors occlude every overlapping cell; indexed wall/climb exceptions
  must not expose a wide combat pose's feet through the next parapet.
- Animation/AI tests use one controlled clock for both input callbacks and
  scheduled ticks. Repainting and key-repeat must not advance AI timers.

## Recovery Workflow

Before extending a subsystem, recover its whole ordinary routine and list
each condition, outgoing branch and state field. Check its callers and the
order of frame loading, terrain updates, decisions and rendering. Keep
untranslated branches named rather than silently inventing their behavior.

Implement that branch in its owning module. Add boundary tests and an
integrated scenario that continues past the visible symptom: room arrival
plus subsequent frames, or player fall/death plus the NPC's completed brake.
Use reference video to validate pose order, geometry and conditional drawing;
passing a test for an approximation is not proof of original-game parity.

This map is a starting inventory, not an exhaustive branch catalog of the
whole game. The next useful recovery work is the remaining rooftop wall,
clipping, special grab/climb cases, additional tumble variants and NPC terrain routines
before expanding to more levels.

[RECOVERY_INDEX.md](RECOVERY_INDEX.md) now tracks branch-level status,
including unnamed helpers and explicit port safeguards. Its linked
[RECOVERY_CATALOG.csv](RECOVERY_CATALOG.csv) covers the 1,198 named routine
markers, defaulting to `indexed-only` where no semantic review is recorded.
It is not a completion percentage. Run `python -m tools.recovery_catalog --check`
to verify that the catalog matches its source inventories/current reviews.

The r3 subset adds GenCtrl's solid-barrier automatic short step at distance
<27 (6:11a0), front/rear sword bumps 64/65 (4:64f6), all eleven native rooftop
decoration entries (23:018e, DATA cca8/ccea), and per-guard drawing state.
F2 peaceful mode is a separate developer feature: it disables NPC simulation
and rendering, never floor/wall physics. A collision that replaces the
sheathing sequence must also clear its host-side command lock. Corpse
visibility at the screen-5 lip is retained as a known visual difference.

Rooftop fatal tumbles use DoOppTumbleSeq 4:0154-02cc and CheckStab
6:56ba-56d4. GetCellsBehind 4:3a48 checks behind the supporting foot, not
the actor's front tile. The r12 subset includes forced falls and the native
generator LIFE flag, random roll, registered-death count, corpse overlap,
facing and tile vetoes. SEQS:185 falls in mode 9 without ordinary floor,
wall or room-cut handling; ordinary-room drawing bypasses actor occlusion.
GetOppDeadSeq 4:0074-010a selects flat corpse pose 228 for odd guard slots,
not randomly. Special-actor corpse variants and special-room tumble clipping
are still missing. Flat-corpse visibility at the screen-5 lip is retained as
a known visual difference. Parry remains limited to poses 150/161:
raised counterattack pose 162 is vulnerable.

## Public Repository Boundary

The native port is a separate project from Mini vMac DX. Its implementation,
tests, documentation and extraction tools are self-contained. Local virtual
environments, caches and generated renders are excluded by `.gitignore`.
Original resource files and enemy data in `assets/` are also excluded. The
first-run importer generates them from a user-supplied disk image; the image
and game executable are not copied into the source distribution.

Newly written contributions are covered by the [MIT license](../LICENSE). Original
game resources and extracted data are outside that grant, including the
contents of `assets/` and original tables embedded in code or tests. See
[third-party notices](../THIRD_PARTY_NOTICES.md) for the scope. No redistribution
permission for original game content has been established. ROMs, disk images,
disassemblies and personal recordings are not part of this project folder.
