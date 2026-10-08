# Rule Recovery Index

The original executable/resources are preserved locally. All CODE bytes were
extracted, but the original high-level source has not been recovered. Static
disassembly, including known function names, is not proof that every branch,
indirect call, global state field or update-order dependency is understood.

## Routine Catalog

[RECOVERY_CATALOG.csv](RECOVERY_CATALOG.csv) lists all 1,198 original named
routine markers from the original symbol index, with their segment,
probable body offset, current review scope and known call-site counts.
`python -m tools.recovery_catalog --check` checks review entries against the bundled
catalog. Use `--source PATH_TO_RECOVERY` to re-index the original `symbols.csv`
and `named_calls.csv`; those research files are not needed to run the game or tests.

- `indexed-only`: located by the extraction, with no semantic review recorded
  in this prototype catalog. This does not claim nobody ever inspected it.
- `reference-only`: consulted, but the original routine is not translated.
- `partial`: specific ordinary branches are used by the prototype. The rest
  of the routine is not certified, even if the listed regression tests pass.

These are routine markers, not 1,198 gameplay rules. Some routines are library
code; some gameplay routines/helpers have no recovered name. The branch list
below includes relevant unnamed helpers. Neither list is an exhaustive count
of all conditions. No completion percentage is assigned.

## Branch Ledger

`T` means the stated subset has implementation and regression coverage.
`R` means recovered/reference logic still needs translation.
`P` means the exact behavior remains pending. `A` identifies a port safeguard
or approximation, not a literal translation. Source addresses are CODE:offset.

| Rule / condition | Source | Status and scope | Owner / tests |
| --- | --- | --- | --- |
| Keyboard sample priority; ordinary Forward + Up selection | 2:55d2; 6:0dbe-0dca | T: directional priority and ordinary chord subset; not a native single-command buffer | mac_input / test_animation_data |
| Host single-command buffer; legal pose transitions; held repeat | 6:0c32, 1014, 11e4; 4:3e84 | T/A: tested transitions; host buffer is not the complete native per-direction -1/0/1 input state | scene_prototype / test_animation_data |
| Five unarmed / six armed Macintosh ticks | 2:68c8 | T: timer branch | scene_prototype / test_animation_data |
| Original pose chains, offsets and attachments | FRAM/AFRM/SEQS/SHAP; 4:2c0c | T: used interpreter operations; others fail explicitly | sequence_runtime / test_animation_data |
| Supporting-foot tile, signed column/row | 4:3a72, 3ad6, 3afa | T: ordinary actors | terrain / test_terrain |
| Floor checks require FRAM 0x40 | 4:35ba | T: ordinary rooftop subset | terrain / test_terrain |
| Fresh forward press, solid barrier type 1, distance <27 | 6:11a0-11d6 | T: short step without Shift; strict threshold | scene_prototype / test_game_ui |
| Shift step reserves four pixels; caution then deliberate step | 4:5eae; 6:1276-1324 | T: floor/gap/ordinary wall; special barrier states P | terrain/mac_input / test_cautious_step, test_terrain |
| Run release at native stop gates; queued follow-up | 6:11e4; SEQS:13 | T: ordinary run; 33-pixel stop displacement at both feet audited | scene_prototype / test_animation_data, test_guard_deaths |
| Standing crouch 50 versus running crouch 26; input at first low pose 109 | 6:0f4e/1068-108a, 125a, 06b4/099a; SEQS:50/26/117/79/49 | T: ordinary crouch, release/crawl gates and wall response; pickup/special-level branches P | scene_prototype / test_animation_data, test_game_ui |
| Running-jump landing clears pending directional inputs, then resamples held keys | 6:074a-0760, 1216-1248; 4:3e3a/3e84; SEQS:4 to 201 | T: pose-44 reset, released/held Up, opposing chords, backward-before-Up priority; both directions | scene_prototype / test_animation_data, test_game_ui |
| Other ClearControls sites and full directional/modifier latch lifecycle | 6:059c, 0754 (pose 26); 4:3cae-3f42 | R: ordinary lifecycle and 31 decoded direct clear calls audited; integration missing, special contexts P | INPUT_RECOVERY / test_input_recovery (four expected failures, not parity coverage) |
| Running jump takeoff checks next two cells | 6:1c14-1d3a | T: ordinary player/NPC subset | terrain / test_terrain, test_rooftop_pursuit |
| Draw reserves 56 against gap/solid wall; combat turn reserves gap space | 6:2072-2122, 26dc-276c | T: ordinary rooftop floor/gap/wall; full gate/special branches P | terrain / test_terrain, test_game_ui |
| Standing turn bypasses barrier response; unarmed grounded contact ignores rear wall | 4:4e46, 551a/5586 | T: ordinary exclusions within port sweep; full collision buffers P | terrain / test_terrain, test_game_ui |
| PutSwordAway clears sword mode before first pose, while animation remains locked | 6:2594; SEQS:92/93 | T: ordinary sword lifecycle, full post-retreat sheath | scene_prototype / test_game_ui |
| Ctrl while running preserves stop-and-draw intent | host QoL, not native queue parity | A/T: intentional extension; original draw poses retained, short/held Ctrl and both facings tested | scene_prototype / test_input_recovery |
| Wall bump keeps the used Up press consumed until release, preventing a phantom jump | host input lifecycle; 23:31 comparison video | A/T: release/held-state fix, not a recovered native keyboard routine | scene_prototype / test_game_ui |
| Front sword bump 64 versus rear sword bump 65 | 4:64f6-6532 | T: ordinary grounded wall response | terrain / test_game_ui |
| Collision response's wider pose stays outside solid wall | 4:6534-6546 reloads pose | A/T: second body sweep after response; full native buffers P | terrain / test_game_ui |
| Body touches exclusive wall edge without overlap; right-facing step clearance conversion | 4:53b8-53ca, 65d8-65ea | T/A: native edge semantics within port body sweep; short steps and actual bumps retained | terrain / test_terrain, test_game_ui |
| Fall preparation uses old supporting foot/column | 4:4b16-4d90 | T: ordinary rooftop preparation | terrain / test_terrain |
| Gravity +6 capped at 63; landing thresholds 50/63 | 4:341a, 3464; 6:00a6, 0280 | T: ordinary player/NPC falls | terrain / test_terrain |
| Catch velocity <60 and height [-48,+3] | 4:37ca; 6:011e-0132 | T: ordinary rooftop catch | terrain / test_game_ui |
| Wall-backed hang settles once, mode 6 bypass; free-air expiry | 6:18e0, 1926; SEQS:25 | T: tested wall/gate distinction and free-air branch | terrain, scene_prototype / test_game_ui, test_terrain |
| Up climb takes priority over Shift release | 6:18e0; SEQS:10/235 | T: ordinary ledges | scene_prototype / test_game_ui |
| Ledge release chooses floor return 11 / free fall 23 with relative offset | 6:1a84-1b7c; 3:4e32 | T: ordinary wall/floor/empty subset; empty-cell DoJumpHang/99 and special levels P | terrain, scene_prototype / test_terrain, test_game_ui |
| Blocked climb destination / special-level grab variants | remaining GenCtrl/Catch branches | P | terrain / new recovery needed |
| Horizontal cut bounds and exclusions; down-first rule | 6:4918, 4a26, 4dac | T: supported horizontal subset; full vertical timing P | terrain / test_terrain |
| Per-actor near facade/parapet versus shaded side | 3:35bc; CODE:23; 4:4146 | T/A: row/mode masks; full native ClipChar R | render_opening / test_render_opening, test_game_ui |
| Prince flat-death edge alignment and settled-rooftop corpse visibility | 6:551c-5558; 4:474c-477c, 4846-485c | T: ordinary Prince/guard dead poses, native room-15/16/19 visibility exceptions | combat, terrain, render_opening / test_rebirth, test_render_opening |
| Ordinary guard death cue and post-kill sword lowering | 6:570e/5738; 4:09c0; 6:2536/25ee | T: type-2 guards on LEVL 21a4 == 0; ready-pose gate preserves unfinished attacks | combat, rebirth / test_combat, test_rebirth |
| Dead actors cannot enter a live wall bump during death | 4:5740-5746 | T: Collide returns before displacement/response; shared Prince and guard life gate | terrain, scene_prototype / test_guard_deaths, test_rebirth |
| All 11 roof decoration IDs, including empty cells | 23:018e-0242; DATA:cca8/ccea | T: native shape/offset/pass tables; conditional draw pipeline P | render_opening / test_render_opening |
| Climb partial foreground rectangle / ledge overlap veto | 3:3694; 23:0614 | T: tested ordinary poses and overlap exception | render_opening / test_render_opening |
| Guard corpse's flat-floor placement and supporting foot | 6:04aa, 5524-5558; SEQS:85 | T: source coordinate/edge subset; settled rooftop visibility uses IsCharNonViewable | terrain/combat/render_opening / test_terrain, test_render_opening |
| Corpse tumble selection: forced or room generator life 0x80, dead bank/Rnd(3), same-cell corpse, facing/tile vetoes | 4:0154-02cc, 03f4; 6:406e, 56ba | T: ordinary supported rooftop subset | combat/opponent_generation / test_guard_deaths, test_rooftop_pursuit |
| Mode-9 tumble bypasses walls/floors/cuts; absolute row/gravity; offscreen Y=730 | 2:65ee-6664; 4:341a/36a2-36ec | T: ordinary supported rooftop subset | terrain / test_guard_deaths |
| Flat corpse 195/228 for odd slot, 185 for even slot; no RNG | 4:0074-010a; 2:6544-654c | T: ordinary ordered room slots; full native bank lifecycle P | combat / test_guard_deaths, test_opponent_generation |
| Mode-9 character clipping bypass and harbor water cap | 4:4210-422c; 23:0826 | T: ordinary rooftop bypass and native harbor 354/327 waterline subset; conditional pillar ordering P | render_opening, scene_prototype / test_guard_deaths, test_harbor |
| Skill tables, initial guard/generator data | DATA/LEVL; 6:3a0c | T: extracted ordinary rooftop profiles | enemy_profiles/opponent_generation / test_enemy_ai, test_opponent_generation |
| Ready-pose advance/retreat checks own anchor column | 4:0a82-0b1a; 6:2c90 | T: ordinary guard subset, not immunity to falling | combat / test_enemy_ai, test_rooftop_pursuit |
| Pursuit, gap jump and incoming reinforcement corridor | 4:057c/0834; 6:1c14/3a0c | T: supported rooftop paths; inactive-world/special actors P | combat / test_rooftop_pursuit, test_opponent_generation |
| Parry/contact poses, range, damage priority | 6:50ec/523e/53f8/5978 | T: ordinary actors; special attacks P | combat / test_combat |
| Jump cannot pass a live grounded opposing guard | 2:6c64-6daa | T/A: native gates plus port between-frame sweep | combat / test_game_ui |
| One-life meter flashing | 2:5442-546c | T: simulation-frame parity; upgrade effects P | combat_art / test_combat |
| Window escape and glass timeline | 2:5d56; CODE:23; DATA/SEQS | T: isolated opening with glass cue | opening_animation, audio / test_opening_animation, test_audio_integration |
| Opening story, title and audio synchronization | 15:45c2/4ee8/6f1a/6fec; CODE:16 SCRP; NIS/Title archives | T: recovered coordinator calls, native scene/audio program; pixel parity P | intro, extract_intro / test_intro, test_extract_intro, test_intro_scene |
| Title cloud composition, initial fade and finite playback | 15:7014-7060/7178-7224; 16:0366-0468/14be-14d4; Title SCRP:25004 | T: signed rear-cloud coordinates and original scene deadlines; QoL: continuous cloud motion through both fades, verified seamless script repetition | intro / test_intro, test_intro_scene.OriginalTitleTests |
| Story lettering baselines and three horizontal shadow/color passes | 15:0302-03ae/2976-2982; 17:0694/0b40-0b4c/294e-29ba/28de/2b9a; FOND:213/NFNT:24878 | T: ordinary intro subtitle layout, leading-space skipping, decorative-initial origin and reserved display black at index 255 | intro / test_intro |
| Two-pass 2x1-pixel dissolve and cached group order | 15:2d7a/31ba-3256; Prince2.opt DSLV | T/A: per-group alternating word offsets verified against native CPU writes; original cached permutation, deterministic fallback when cache absent, native Random seed P | intro, extract_intro / test_intro, test_extract_intro |
| Visible 510x384 rectangle and host presentation | 17:1ada-1b00; NIS SHAP:25001 | T: native extent, cropped host padding, nearest-neighbor fitting and inverse pointer mapping | game_ui, window_controls / test_game_ui, test_development_menu |
| Prince environment palette | 3:5f1c-5f44; LEVL:2186; Kid CTBL:25001-25006 | T: palette 25000 + environment kind, independent of SHPL/FRAM bank; rooftop CTBL 25005 | render_opening, scene_prototype / test_palettes, test_game_ui |
| CUST full-room background and foreground | 3:1378/142a/2324; CUST:4350 | T: fixed level-1 descent-room images and draw passes; animated custom templates P | render_opening / test_harbor |
| Harbor floor, pillars and waves | 23:0248, 0d1c/0dce; DATA:cc32/cc3a | T: native SHAP/PIEC offsets, phase cycle and wave clip rectangles; native random phase seeding / conditional redraw P | render_opening, harbor / test_harbor |
| Ship activation, two-pixel drift and departure limit | 2:5374; 23:1066/1120/1256 | T: level-1 counter, entry-pose reset and original SHAP layers; full native obstacle-bank lifecycle P | harbor, render_opening / test_harbor |
| Ship catch, grip movement and boarding sequence | 23:12ba/12f0/132c; SEQS:59 | T: strict X/row/time bounds, relative movement and complete original pose chain | harbor, terrain, scene_prototype / test_harbor |
| Water entry, splash and delayed death; harbor exception at Y=730 | 23:06fe/0b3e; 4:36ae-36ec | T: player/NPC thresholds, exemptions, six splash poses and eight-frame death delay; host stores one splash per actor rather than the native shared slot | harbor, terrain, scene_prototype / test_harbor |
| Boarding requests level transition (-16), then holds invisible pose | 4:2f2c; 6:5022; SEQS:59/215 | T/A: original request and sequence translated; host completion screen substitutes for the unported movie / next-level loader | sequence_runtime, scene_prototype / test_harbor |
| Dynamic tiles/gates, ceilings, other levels and full level-transition pipeline | remaining level/controller routines | P | not yet ported |
| Dead-pose counter, any-key retry and centered restart message | 2:47e6/7148; 4:3b88/47a0; 3:433a | T: ordinary dead-pose/key gate and actual current/pending playback completion; frontend timeout P | rebirth, audio, scene_prototype, window_controls / test_rebirth, test_audio |
| Audio cue arbitration, source samples and rooftop music pool | CODE:5; DATA; INST/snd; MIDISnd/DigiSnd | T/A: ordinary level-1 subset; original instruments with host sampler, not bit-exact Mac MIDI driver | audio, audio_formats, extract_audio / test_audio, test_extract_audio, test_audio_integration |
| LEVL checkpoint trigger and restored start | LEVL:39a6; 2:6b46/1674/19ba/5d50 | T: level-1 foot/cell trigger, native anchor, facing/full life and opponent/generator snapshot; dynamic normalization/story pipeline P | rebirth, scene_prototype / test_rebirth |
| F2 screen jumps seed the latest route checkpoint from LEVL | host feature | T: route order rather than slot order; earlier/secret jumps and F5 clear it; not an original activation rule | scene_prototype / test_rebirth |
| In-game F2 menu, peaceful scene, ordinary-key/click pause resume, Windows fullscreen | host features | T: font, modal input, modifier/media/navigation/system-shortcut exclusions, held-key consumption and focus reset; not recovered Mac gameplay rules | window_controls/game_ui / test_game_ui, test_development_menu |

## Corpse Visibility

The former guard-only visibility exception could leave either a small strip
above the parapet or a whole flat corpse exposed over a sloping edge.
Settled Prince and ordinary guard corpses now follow the explicit native
IsCharNonViewable rule, including guard pose 228. This changes drawing only:
death sequences, coordinates and stored NPC records remain intact.

## Next Recovery Pass

1. Complete ordinary GetCharEdges/Collide/ClipChar and rooftop draw-pass
   dependencies and climb stages.
2. Extend the branch ledger with each predicate, caller, global field and
   outgoing branch, marking unimplemented branches explicitly.
3. Add boundary tests and a reference scenario before changing that branch's
   owner. Renderer changes must not conceal incorrect terrain positions.
4. Recover dynamic tiles and special destinations before claiming that the
   first level's rules generalize to the whole game.

The broader subsystem map remains in [BEHAVIOR_MAP.md](BEHAVIOR_MAP.md).
Neither this ledger nor green tests certify complete original-game parity.

## Input Audit

[INPUT_RECOVERY.md](INPUT_RECOVERY.md) maps the five native input latches,
sampling order, ordinary controller priorities and all 31 decoded direct
ClearControls calls. It distinguishes recovered rules from translated behavior.
`tests/test_input_recovery.py` tracks four demonstrated gaps as expected
failures; these are not passing parity coverage. The full native latch lifecycle
still needs integration, without changing the established animation clocks.
