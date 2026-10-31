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
`python -m tools.recovery_catalog --summary` prints the recorded review counts
without modifying the catalog. These counts include all subsystems, not just AI.

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
| Cavern movement17 internal sustain loop and cue admission | WAVE9769;20:3b2a,37a8,467c;5:4d84,5122,530a;16:25fe | T: intro once, block5025..11520 repeats; import metadata/exact legacy PCM recognition; SDL capture192000 frames exact;516 native admission checks. Hardware timing P; mixed-effects policy intentional | audio_loop / test_audio_loop / probe_stone_gate_audio / research/stone-gate-opening-audio |
| Undefined cells past missing links (all environments); silent non-rooftop void death preserves falling scream | 4:28b6-29b8, 374a-3786; 5:4b5a | T: rooftop air, ruins top-row air and level6 room27 / level9 room16 exteriors, temple level-13 chasm rooms, palace rooms 3/7/8 (temple/palace/top-row branches since 2026-10-31); 19,794 native undefined-cell comparisons over LEVL 2000-2013 and 63 terminal death calls with DecLifePts/SetMode recorded; full FrameAdv and audio waveform parity P | terrain, scene_prototype / probe_cliff_void, test_cliff_map_fixes |
| Entrance door final slam reaches the split closing audio lane | 5:15bc-161a, 25aa-25f8 | T/A: existing native exported entry phases/cue20 retained; source/direction attributed for intentional concurrent audio | cavern_state / test_cliff_map_fixes, test_gate_audio |
| Discovery after level three and fresh level-four arrival | 2:0180-027e; 15:1a76 | T: native coordinator import, three callback-free flags-6 animations, bank-separated audio, pause/skip/F3 and life retention; tree/live clock/onward progression P | extract_intro, intro, scene_prototype / test_discovery |
| Keyboard sample priority; ordinary Forward + Up selection | 2:55d2; 6:0dbe-0dca | T: directional priority and ordinary chord subset; not a native single-command buffer | mac_input / test_animation_data |
| Host single-command buffer; legal pose transitions; held repeat | 6:0c32, 1014, 11e4; 4:3e84 | T/A: tested transitions; host buffer is not the complete native per-direction -1/0/1 input state | scene_prototype / test_animation_data |
| Five unarmed / six armed Macintosh ticks | 2:68c8 | T: timer branch | scene_prototype / test_animation_data |
| Original pose chains, offsets and attachments | FRAM/AFRM/SEQS/SHAP; 4:2c0c | T: used interpreter operations; others fail explicitly | sequence_runtime / test_animation_data |
| Terminal -23 rewinds from entry cursor and rereads the resource pose after reload | 4:2f00-2f14 | T: 867 independent original AnimChar checks; other opcode/callback paths retain their own scope | sequence_runtime / test_sequence_holds |
| Opcode -18 clears selected ID; links retain zero until JumpSeq | 4:2d7e-2d84 | T: native selected-field clear, second skeleton shake and zero-ID snapshot regression; existing extra mode clear inert in audited ordinary paths | sequence_runtime, save_game / test_sequence_holds, test_skeletons, test_save_game |
| One +0x34 word: SEQS -21, lava 5 and attract word 26 share `sequence_mode` | 4:2f92, 471e; 6:23b2; 8:3546; a5-0x5022 | T: `special_flag` merged (2026-10-31); SEQS:232 -21 13 reaches the guard brake/OppToFight; legacy saves keep whichever field was set; Kid lava also writes 5; unmodelled native readers listed P | sequence_runtime, save_game, combat / test_enemy_ai, test_save_game; [readers](research/animchar-op18-selected-sequence.md) |
| Silent animation callback zero sets only the Prince's movement signal | 4:30e0-30f6/314e-315a; SEQS:11/227 | T: 72 original callback calls + 288 independent AnimChar resource cases; complete noise/scheduler lifecycle P | sequence_runtime / test_sequence_noise |
| Selected SEQS survives -1 links; -8 assigns velocity with 10000 sentinel | 6:0006; 4:2ec2, 2ff4-3018 | T: hurt/turn allowance and repeat sword-retreat catch; -9 is a separate additive opcode | sequence_runtime/terrain / test_animation_data, test_terrain |
| Supporting-foot tile, signed column/row | 4:3a72, 3ad6, 3afa | T: ordinary actors | terrain / test_terrain |
| Ruins crevice fronts and floor decorations retain overlapping cavern torch IDs | 7:2344-24ae, 282e-295c | T: environment-scoped live filter; 102 item-free room drawings and revealed tunnel regressions; whole import/renderer P | caverns / test_ruins_scenery_items; research/ruins-scenery-pickup.md |
| Sword pickup admission and held-Shift resampling | 6:1350-13c0, 0c50-0c66; 4:3a72/3ad6 | T: 2200 native admission comparisons and3520 held/clear gate calls; complete GenCtrl and pickup effects P | potions, scene_prototype / probe_item_pickup, test_level6; research/ruins-scenery-pickup.md |
| Floor checks require FRAM 0x40 | 4:35ba | T: ordinary rooftop subset | terrain / test_terrain |
| Fresh forward press, solid barrier type 1, distance <27 | 6:11a0-11d6 | T: short step without Shift; strict threshold | scene_prototype / test_game_ui |
| Shift step reserves four pixels; caution then deliberate step | 4:5eae; 6:1276-1324 | T: floor/gap/ordinary wall; A: gates in every environment (213,600 original/production 4:5eae cases at every LEVL 2000-2013 gate: desert phases 0-20, heights, sequence 68, caution) since 2026-10-31, a barrier 51+ away reports 42; callers and other special barrier states P | terrain/mac_input / test_cautious_step, test_terrain, probe_gate_barriers; [scope](research/gate-barrier-distances.md) |
| Run release at native stop gates; queued follow-up | 6:11e4; SEQS:13 | T: ordinary run; gates 7/11 only, 33-pixel stop displacement and stop/turn/descent positions audited | scene_prototype / test_animation_data, test_guard_deaths, test_game_ui |
| Standing crouch 50 versus running crouch 26; input at first low pose 109 | 6:0f4e/1068-108a, 125a, 06b4/099a; SEQS:50/26/117/79/49 | T: ordinary crouch, release/crawl gates and wall response; pickup/special-level branches P | scene_prototype / test_animation_data, test_game_ui |
| Same directional bank through ordinary crouch/rise and prone movement | 6:0576-059c, 07ee-0b58, 1068-10e2 | T/A: reused76,357-call native audit;25,928 production/model cases; protected rise/prone clears and fresh-input priorities; explicit held-step/release tolerance and separate source46 owner; geometry/FrameAdv parity P | low_controls, mac_input / test_low_controls; [scope](research/low-input-handoff.md) |
| Armed OnAlert request priority and conflicting buffered requests | 6:24bc-2584 | T/A:19,440 original/model request cases; Ctrl/Down/Up/Forward/Backward priority and supplied recoil/special boundaries; interim host-slot arbitration, not armed bank/action/outer SwordCtrl parity | sword_controls, scene_prototype / test_armed_input, probe_armed_input; [scope](research/armed-input-priority.md) |
| Iron-gate sounds outside the caverns | 5:42b4-4426, 14b6-14cc; ATMExit 5:15c0 | T: environment 3 keeps 17/18/20; others 272 moving (every eighth rising pixel), 273 opened, 274 stopped, 275 slam; exit doors unchanged; Macintosh recording comparison P | pressure_plates, audio / test_pressure_plates, test_gate_audio; [scope](research/stone-gate-opening-audio.md) |
| Outer SwordCtrl routing: distance gate and direct sheathe | 6:2166-2390; 4:35a6; 6:2592 | T/A: 3,538,944 original/model routing cases (cell kind, opponent alert a5-0x5062, distance, turn flag, type-6 and bridge exemptions); unengaged pending Down sheathes at any mode-0/1 pose ahead of an attack; type-6/bridge/cell turn exemptions in production; action bodies P | combat, armed_controls / test_armed_input, test_combat, probe_sword_ctrl; [scope](research/armed-input-priority.md) |
| Level-five bridge engagement for the skeleton and the Prince | 8:02ae, 8:0188, 8:0424, 8:0458 | T/A: 1,244,160 original/production cases; facing left presses from bridge column 8, right below 2, toward the open gate or an armed opponent ahead on a taut bridge (port sides were swapped until 2026-10-31) | bridge, combat / test_bridge, probe_bridge_engage; [scope](research/armed-input-priority.md) |
| Nearly cleared running pose ignores trailing contact at cavern gates | deliberate port improvement, not a recovered native rule | A/T: four-pixel ordinary margin; stop13 may settle when its idle body plus final backward pixel fully clears the gate; grounded unarmed run/start/stop only, either facing; front/settled-body contact, jumping, crouching and crush/slam timing unchanged | terrain / test_gate_clearance, test_cavern_retry; [scope](CAVERN_GATE_CLEARANCE.md) |
| Running-jump landing clears pending directional inputs, then resamples held keys | 6:074a-0760, 1216-1248; 4:3e3a/3e84; SEQS:4 to 201 | T: pose-44 reset, released/held Up, opposing chords, backward-before-Up priority; both directions | scene_prototype / test_animation_data, test_game_ui |
| Other ClearControls sites and full directional/modifier latch lifecycle | 6:059c, 075c (pose 26); 4:3cae-3f42 | R/T: 14,265 original bank/reset cases; early-jump, horizontal crouch-rise and released-Ctrl counter gaps corrected; full bank integration and special contexts P | INPUT_RECOVERY / probe_input_bank, reference_input_bank / test_input_bank, test_input_recovery |
| Running jump takeoff checks next two cells | 6:1c14-1d3a | T: ordinary player/NPC subset | terrain / test_terrain, test_rooftop_pursuit |
| Draw reserves 56 or is refused; combat turn reserves gap space | 6:1f04-2154, 26dc-276c; 4:35a6, 39fc, 3a48, 5b0e, 5eae; 3:4da6 | T/A: 262,056 original/production DoKidEngarde cases over LEVL 2000-2013 (terrain sweep, poses 246-262, modes 0/2/4; gates in, behind and ahead of the supporting cell); refusals (desert, obstructed behind, mode 4, poses 246-261), loose floor/gates ahead since 2026-10-31, zero mismatches once GetUndefineCellId's temple/palace branches were translated; temple sliding rock, type 1 P | terrain / test_terrain, probe_kid_engarde; [scope](research/gate-barrier-distances.md) |
| Prince sword turn reserves space at walls, gaps and blocking gates | 6:26b8-277a; 4:39fc, 27ee, 3a72-3ac8, 2bae, 5b0e; 3:4da6 | T/A: 316,128 original/production cases over LEVL 2000-2013 (terrain sweep, gate phases/heights/types 0-1/sequence 68, 94/207 allowances, breaking-bridge refusal); the desert gate blocks below phase 19 and the temple's by height since 2026-10-31; callers and opponent turn branches P | terrain, combat / test_terrain, probe_prince_turn; [scope](research/prince-turn-routine.md) |
| Standing turn reserves foot space before a blocking gate | 6:10f6-1158; 4:39fc, 27ee, 3a72-3ac8, 2bae, 5b0e | T/A: 383,490 original/production cases over LEVL 2000-2013 (terrain sweep; every gate, desert phases 0-20, heights, type 1, sequence 68); 11 pixels in the caverns, none at the throne, 6 elsewhere since 2026-10-31; SEQS 5 selection and the 6:10e4 prologue P | terrain / test_terrain, test_stone_gates, probe_standing_turn; [scope](research/gate-barrier-distances.md) |
| Standing turn bypasses barrier response; unarmed grounded contact ignores rear wall | 4:4e46, 551a/5586 | T: ordinary exclusions within port sweep; full collision buffers P | terrain / test_terrain, test_game_ui |
| PutSwordAway clears sword mode before first pose, while animation remains locked | 6:2594; SEQS:92/93 | T: ordinary sword lifecycle, full post-retreat sheath | scene_prototype / test_game_ui |
| StartFall clears sword mode before selecting the fall sequence | 4:4ca8-4cb2 | T: ordinary fall entry, including Shift catch after sword retreat from the initial roof | scene_prototype / test_terrain |
| Ctrl while running preserves stop-and-draw intent | host QoL, not native queue parity | A/T: intentional extension; original draw poses retained, short/held Ctrl and both facings tested | scene_prototype / test_input_recovery |
| Wall bump keeps the used Up press consumed until release, preventing a phantom jump | host input lifecycle; 23:31 comparison video | A/T: release/held-state fix, not a recovered native keyboard routine | scene_prototype / test_game_ui |
| The Kid's Collide response (bump 64/65, 46/47, prone 121, GroundBump 45, fast-fall backoff) | 4:5738-5a54, 5868, 589e; 4:2bae; 6:5d60 | T: since 2026-10-31 the response moves like 4:592a-5998: rear 65 six forward (17 more from SEQS 55 pose 207), front 64 from strike poses 153/154/244/245 25 forward, vertical speed 50+ backs off 17 with no bump, GroundBump ten back (state 4 only stops); the displacement itself is still the port's swept correction, not CheckBarr's; open-gate suppression (cell cache tile 4 > 60) and the temple rock 93 not wired; Codex's reference probes (temple-armed-collision, temple-ground-*) cover the branches natively | terrain / test_terrain, test_game_ui; [scope](COLLISION_RECOVERY.md#the-kids-collide-response) |
| An extended scythe is a barrier for a tall body | 4:5654-5674, 5c76; 5:5fa0; 4:52bc (code 6) | T: tile 12 at phase 3-15 stops bodies taller than 48 (actors 1/7/8/11 pass) with barrier 6 edges +8/-16; the port walked through it before 2026-10-31 | terrain / test_terrain; [scope](COLLISION_RECOVERY.md#the-kids-collide-response) |
| Opponent wall and gate contact (EnemyCollide) | 4:62b0-654a; 4:5654, 5ade, 5b0e, 52bc, 6562, 6610, 56e6; 3:1ab0, 4ef2 | T/A: 511,788 original/production cases over LEVL 2000-2013 (barrier and gate sweeps, preconditions, types 2/4/5/6/11); armed opponents in animation state 1 take SEQS 65 and the nearer distance since 2026-10-31 (formerly the Kid's swept Collide, 64 with cue 10), zero mismatches; other opponent states keep the port's swept correction (exception); heads separate | terrain, combat / test_terrain, probe_enemy_collide; [scope](research/opponent-barriers.md) |
| Dormant-opponent proximity path (OpponentClose) | 4:13a4-14b2, 1486; 3:4da6, 4de2; 4:5b0e | T/A: 222,412 original/production cases (terrain sweep, reaches 4/5/8, types 4/10, every gate); type 10 crosses impassable cells, gates use the shared 4:5b0e; shake-timer branch and 4:14c6 P | skeleton / test_skeletons, probe_opponent_close; [scope](research/opponent-barriers.md) |
| Opponents pushed out of a blocking gate (CheckGateForOpp) | 4:5ffc-60e2, 6202-62ae, 541a, 547c; 2:65fa | T: 198,966 original/production cases over LEVL 2000-2013 (every gate and phase, room edges), 0 mismatches; new since 2026-10-31 (the port had none); heads and opponents outside the Kid room P | terrain / test_terrain, probe_gate_for_opp; [scope](research/opponent-barriers.md) |
| Opponent draw at pose 166: rear step 8, DoEngarde reserve 18 | 4:4996-49ea; 6:1e78-1ef4; 4:5eae, 3a48; 6:5eca | T: 241,290 original/production cases over LEVL 2000-2013, 0 mismatches outside 6 temple cases (level 13 room 4); rear cell by column word and pre-step 5eae geometry since 2026-10-31 | combat, terrain / test_enemy_ai, probe_opp_engarde; [scope](research/unarmed-runner-brake.md) |
| Opponent physics admission by native X window and special rooms | 2:6550-65d6 | R/T: static branch translated 2026-10-31; AnimChar still runs outside it | combat / test_enemy_ai; [scope](research/unarmed-runner-brake.md) |
| Cavern dart flight against walls, gates and the row above | 8:2f98-312a; 4:27ee, 5b0e; 3:4eb2, 4ef2; 5:29e8-2b0e | T/A: 133,392 original/production updates (cavern LEVL, view/left/lower rooms, retiring velocities, every gate); DIVS columns since 2026-10-31; the body 4:5b0e reads is the copy the previous frame left (MakeRubble 5:29e8 dispatch 5:2ab0 loads none; Prince or last opponent), port passes the Prince, unreachable in shipped levels | darts / test_darts, probe_mob_dart; [scope](research/opponent-barriers.md) |
| Collision response's wider pose stays outside solid wall | 4:6534-6546 reloads pose | A/T: second body sweep after response; full native buffers P | terrain / test_game_ui |
| Body touches exclusive wall edge without overlap; right-facing step clearance conversion | 4:53b8-53ca, 65d8-65ea | T/A: native edge semantics within port body sweep; short steps and actual bumps retained | terrain / test_terrain, test_game_ui |
| Fall preparation uses old supporting foot/column | 4:4b16-4d90 | T: ordinary rooftop preparation | terrain / test_terrain |
| Gravity +6 capped at 63; landing thresholds 50/63 | 4:341a, 3464; 6:00a6, 0280 | T: ordinary player/NPC falls | terrain / test_terrain |
| Catch velocity <60, height [-48,+3], source-99 release look-behind 24 instead of 17 | 4:37ca/3882-3894; 6:011e-0132 | T: ordinary catch and release admission (11,304 native comparisons) | terrain / test_game_ui / test_ledge_catch |
| Wall-backed hang settles once, mode 6 bypass; free-air expiry | 6:18e0, 1926; SEQS:25 | T: tested wall/gate distinction and free-air branch | terrain, scene_prototype / test_game_ui, test_terrain |
| Up climb takes priority over Shift release | 6:18e0; SEQS:10/235 | T: ordinary ledges | scene_prototype / test_game_ui |
| Native hanging input gate and climb/release bank prefixes | 6:18e0-191e, 1998-19d4, 1a84-1a92; 4:3e3a | T/A:1170 original/model cases; same runtime bank through grip/Up/modifier priority, release/climb and grounded return; retained host protected-climb tap/repeat policy explicit; geometry/scheduling parity P | ledge_controls, mac_input / test_ledge_controls, probe_ledge_input; [scope](research/ledge-input-handoff.md) |
| Ledge release chooses floor return 11 / free fall 23/99 with relative offset and swing phase | 6:1a84-1bbc; 3:4e32, 4eb2 | T: ordinary wall/floor/space branches and DoJumpHang preview; special levels P | terrain, sequence_runtime, scene_prototype / test_terrain, test_game_ui |
| Blocked climb destination / special-level grab variants | remaining GenCtrl/Catch branches | P | terrain / new recovery needed |
| Horizontal cut bounds and exclusions; down-first rule | 6:4918, 4a26, 4dac | T: supported horizontal subset; full vertical timing P | terrain / test_terrain |
| Per-actor near facade/parapet versus shaded side | 3:35bc; CODE:23; 4:4146 | T/A: row/mode masks; full native ClipChar R | render_opening / test_render_opening, test_game_ui |
| Prince flat-death edge alignment and settled-rooftop corpse visibility | 6:551c-5558; 4:474c-477c, 4846-485c | T: ordinary Prince/guard dead poses, native room-15/16/19 visibility exceptions | combat, terrain, render_opening / test_rebirth, test_render_opening |
| Desert exit hands over to the caverns by X alone | 18:01e6, 0280-0332; 4:5b0e | R/T: static reading; native room 1, X < 207 ends the level at any exit phase (the collision opens at 19); the port waited for phase 20 until 2026-10-31; the a5-0x4f92/-0x439e bookkeeping and JumpSeq 2 are host-side | environments / test_desert; [scope](DESERT_RECOVERY.md) |
| Non-viewable animation modes skip character compositing | 4:4152; 4:4724-474a | T: modes 4/5/6/7/10/12, fully sunk quicksand Prince; complete ClipChar remains partial | scene_prototype / test_desert |
| Ordinary guard death cue and post-kill sword lowering | 6:570e/5738; 4:09c0; 6:2536/25ee | T: type-2 guards on LEVL 21a4 == 0; ready-pose gate preserves unfinished attacks | combat, rebirth / test_combat, test_rebirth |
| Dead actors cannot enter a live wall bump during death | 4:5740-5746 | T: Collide returns before displacement/response; shared Prince and guard life gate | terrain, scene_prototype / test_guard_deaths, test_rebirth |
| All 11 roof decoration IDs, including empty cells | 23:018e-0242; DATA:cca8/ccea | T: native shape/offset/pass tables; conditional draw pipeline P | render_opening / test_render_opening |
| Climb partial foreground rectangle / ledge overlap veto | 3:3694; 23:0614 | T: tested ordinary poses and overlap exception | render_opening / test_render_opening |
| Guard corpse's flat-floor placement and supporting foot | 6:04aa, 5524-5558; SEQS:85 | T: source coordinate/edge subset; settled rooftop visibility uses IsCharNonViewable | terrain/combat/render_opening / test_terrain, test_render_opening |
| Corpse tumble selection: forced or room generator life 0x80, dead active bank/Rnd(3), rebased same-cell corpse, facing/tile vetoes | 4:0154-02cc, 03f4; 6:406e, 56ba | T: ordinary supported rooftop subset, including selected side records; special corpse predicates P | combat/opponent_generation / test_guard_deaths, test_guard_rooms, test_rooftop_pursuit |
| Mode-9 tumble bypasses walls/floors/cuts; absolute row/gravity; offscreen Y=730 | 2:65ee-6664; 4:341a/36a2-36ec | T: ordinary supported rooftop subset | terrain / test_guard_deaths |
| Flat corpse 195/228 for odd slot, 185 for even slot; no RNG | 4:0074-010a; 2:6544-654c | T: ordinary ordered room slots; full native bank lifecycle P | combat / test_guard_deaths, test_opponent_generation |
| Mode-9 character clipping bypass and harbor water cap | 4:4210-422c; 23:0826 | T: ordinary rooftop bypass and native harbor 354/327 waterline subset; conditional pillar ordering P | render_opening, scene_prototype / test_guard_deaths, test_harbor |
| Skill tables, initial guard/generator data | DATA/LEVL; 6:3a0c | T: extracted ordinary rooftop profiles | enemy_profiles/opponent_generation / test_enemy_ai, test_opponent_generation |
| Held Up is resampled before GenCtrl; Prince late block skips startup, blocked strike can recover through 61 | 4:3cd2-3d0a/3e50/3e60; 6:250c-255e/2844-28e6 | T: 2,116 native control comparisons; both-facing guard/skeleton contacts, repeated defence and attack priority; special actors P | scene_prototype / test_combat, test_animation_data |
| Ready-pose advance/retreat checks own anchor column | 4:0a82-0b1a; 6:2c90 | T: ordinary guard subset, not immunity to falling | combat / test_enemy_ai, test_rooftop_pursuit |
| Selected retreat/turn survives links to combat idle; turn spacing uses front foot and rear cells | 4:0a8c-0c08; 6:2206-22e6/26a8 | T: ordinary close guard subset, both facings and 240-frame turn-loop regression; bridge exceptions P | combat / test_enemy_ai, test_rooftop_pursuit |
| Far pursuit only after high+18 and without attack pause; both empty front cells request recoil | 4:0c14-0c66/0fb8-1098 | T: ordinary first-level guards; native level-5 bridge exceptions R | combat / test_enemy_ai, test_rooftop_pursuit |
| Opposing approaching run/jump waits outside 150/186, rather than advancing | 4:0c2a-0c64 | T: strict boundaries; no probability roll for these branches | combat / test_enemy_ai |
| Shared parry/advance/attack timers decrement per processed NPC, including dead records | 6:4e98-4eb6; 2:64f2-651e | T: ordinary processed NPCs and below-room exclusion | combat / test_enemy_ai |
| Hurt recovery does not add a lock beyond native animation mode | 6:2206-220e; 4:098c-0c6a | T: ordinary NPC modes 0/1 can respond; modes >=2 still reject sword input | combat / test_enemy_ai |
| Opening contact protection does not suspend guard decisions; landing wait is pose/mode-specific | 4:09e6-0a08 | T: advance during airborne escape; wait at distance >=39 for poses 102-117 in mode 5 | combat / test_enemy_ai, test_terrain |
| Jump/hold/climb does not grant blanket sword immunity; same row and height difference <15 required | 6:58aa-592c | T: ordinary actors, native dead/protected-mode exclusions and scene interruption cleanup | combat, scene_prototype / test_combat, test_terrain |
| Waiting NPC spacing versus other NPC; self-nearest obstacle response | 4:0c7e-0f14/0f28 | T: ordinary multi-NPC spacing; R: self-nearest front-obstacle retreat | combat / test_rooftop_pursuit |
| Unarmed runner brake: obstacle, spacing, pass, death/13, exit lunge, 212 rear correction | 4:057c-07fc, 39fc, 3a48, 3a92, 17aa; 6:5eca | T: 75,472 original/production AutoCtrl running cases over LEVL 2000-2013 (terrain and gate sweeps, frame fixtures for opponent and Kid), zero mismatches; cells ahead/behind and the pass read the column words since 2026-10-31 (old anchor rule: 388); crowd 6:36f2 and bank record 6:3642 supplied; pose-166/armed branches and full NPC candidate filtering 6:36f2-3918 P | combat / test_enemy_ai, probe_unarmed_brake; [scope](research/unarmed-runner-brake.md) |
| Pursuit, gap jump and incoming reinforcement corridor | 4:057c/0834; 6:1c14/3a0c | T: supported rooftop paths; inactive-world/special actors P | combat / test_rooftop_pursuit, test_opponent_generation |
| Reinforcement counter gate and running-NPC carry on Prince room cuts | 6:3e56-3e68/44c8-450a/3304/4864 | T: full-word counter test, ordinary running/jump carry, unchanged world X and target-bank membership; complete side-room lifecycle P | opponent_generation, combat / test_opponent_generation, test_rooftop_pursuit, test_terrain |
| Non-following skeleton room records, strict Cut versus row-minus-one saved cells | 4:29d8/322a; 6:3104-3268/472a-485c/2c26-2c3a | T: scoped type-4 save/normalize/reload, 8,000 Cut + 1,200 record + 1,308 reload comparisons; special types and full bank lifecycle P | opponent_generation, combat, skeleton / test_opponent_positions, test_skeletons, test_save_game |
| Ordinary guard room records, explicit five-slot active banks and resumed height | 6:2b7e/2f4e/30b0/33bc; 4:0074/3d64 | T: 1,280 original reloads, 510 height reloads, 384 metadata stores, 1,600 integrated record outputs; full-capacity loss and complete target/control scheduler P | opponent_records, combat / test_opponent_records, test_guard_rooms, test_save_game |
| Prince persistent SwordCtrl target versus temporary Main opponent | 2:62f8-6340; 6:0560-05e6/2174-21fe; 6:5a06/5a48 | T: ordinary persistent cache, temporary Main choice, contact writes and snapshot index; native-ALIVE/HP distinctions preserved; complete frame scheduler P | combat, save_game / test_prince_target_cache, test_opponent_generation, test_save_game; research/proposed-prince-target-layers.md |
| Cached rear target and automatic Prince turn flag | 6:2200-22ea/2638-26b8; 2:5e5c; 6:2344-2350 | T: cached rear-target turn and nearer-arrival regressions; ordinary turn-flag initialization/writers recovered; voluntary turn/toggle not implemented, full-frame parity P | combat / test_prince_target_cache; research/prince-turn-flag-and-rear-target.md, research/voluntary-sword-turn.md |
| Zero-HP resumed skeleton registers death before AutoCtrl recovery | 4:3d64-3d6c, 165c-1708 | T: 128 scoped native lifecycle scenarios / 25,600 frames; full zero-HP alert/target scheduling P | combat / test_skeletons |
| Parry/contact poses, range, damage priority | 6:50ec/523e/53f8/5978 | T: ordinary actors; special attacks P | combat / test_combat |
| Sword-hit burst on first rooftop tumble pose, including long-range fatal contact | 3:0994-09ce/0ba4-0cc6 | T: ordinary NPC mode 9/pose 213, one animation pose, native burst anchor and front-of-roof draw | combat_art, scene_prototype / test_combat, test_terrain |
| Ready hurt poses may turn toward the opponent; alert scan uses supporting columns | 6:2258-22ea; 2:6f76-6f9c | T: ordinary ready/locked poses, wall/gap alert gates and idle opening through three stabs; full column lifecycle P | combat, scene_prototype / test_combat, test_terrain |
| Alert scan endpoint gate exclusion and cavern tile-24 exception | 2:6fc2-6fce, 7084-709c | T: ordinary scan boundaries, live tiles, normalized linked columns; special actors and full bank scheduling P | enemy_alerts, combat / test_enemy_alerts |
| Jump cannot pass a live grounded opposing guard | 2:6c64-6daa | T/A: native gates plus port between-frame sweep | combat / test_game_ui |
| One-life meter flashing | 2:5442-546c | T: simulation-frame parity; upgrade effects P | combat_art / test_combat |
| Head half-point meters and multi-head HUD handoff | 3:4aa0-4aaa/4bc8-4c60 | T: 60 native positive-HP shape/position traces; nearest active-head selection, death/flee/row handoff and level8 room1 regressions; native redraw-cache timing P | combat_art, combat / test_ruins_fixes; research/ruins-head-leaves.md |
| Fleeing heads release nearest-on-side priority | 6:379e-37a6/3946-3970 | T: 15000 native bank selections and14961 nearest-on-side checks, native-ALIVE distinct from HP, both head types and serpent fallback; full frame bank lifecycle P | opponent_selection, ruins_ai / probe_ruins_hud_exit, test_ruins_fixes |
| Level8 exit and throne checkpoint require the father's sword | 5:1f18-1f3c; 2:6b98-6bb6 | T: 300 exit and80 checkpoint admission cases; entrance exit exempt, room23 button host replay and throne checkpoint/retry; full NIS route P | pressure_plates, environments, rebirth, scene_prototype / test_ruins_fixes |
| The ride to the temple ends in level ten's room 22, then level ten starts there | 15:5fd4, 65d4 (TransFunc8), 047a (FlipKids), 66bc (FlipKid); 2:03d4-048a (DrawRoomFromNIS: CTBL 3500 at 64); 2:5dee | T: since 2026-10-31 the import keeps the last shot (exported room, horse and the Kid.rsrc Prince, mirrored; horse palettes at frames 43-46) and level nine leads into level ten when the temple scenery is installed; the a5-0x4fec copy of frame 1 is shown at once (approximation); temple mechanisms not wired | extract_intro, intro, caverns, environments / test_temple_arrival, test_carpet_scene, test_level9_horse; [plan](research/temple-implementation-plan.md) |
| Temple sliding rocks: plate trigger, motion, crush and drawing | 5:1fba-1fda; 10:2152, 1d5c, 1656, 1ca4, 16f6, 1b04, 1456, 1788, 20fe, 180e; 5:2afa, 32f6, 3cee; 6:1a84, 1fba-20f2; 4:589e | T/A: since 2026-10-31 production `slide_rocks` matches Codex's native-checked trigger/motion references (1,000 randomized cases, 0 differences); crush reaction (with the a5-0x3570 width), spike impalement 5:3cee, ledge release 6:1a84, neighbour-room drawing (rectangle projection; drawing position assumed), Collide's SEQS 93 and DoKidEngarde's rock branch (probe rock sweep 237,900 cases, 0 mismatches) wired; CheckBarr rock overlays not yet | slide_rocks, environments, caverns, pressure_plates / test_slide_rocks, test_temple_arrival; [plan](research/temple-implementation-plan.md) |
| Temple trap doors open on a shake or landing and close again | 5:28c8; 6:0210; 10:25aa-26d4, 24fa, 225c-24e8; 3:4168 | T: since 2026-10-31 (Codex's references as production rules): tile 26 becomes space at once, phase 1/75, restored past low phase 16 with cue 27; loop cue 198 (10:24fa/2328) and the opened cell redrawn as space (exported tile-26 slot units); falling temple floors draw pieces 28/29 | trapdoors, loose_floors, terrain, environments, caverns / test_temple_arrival; [plan](research/temple-implementation-plan.md) |
| Temple birdheads are ordinary opponents with Birdhead.rsrc art; LZ-packed shapes | 6:2bca-2c12; 3:5f58; 17:359e, 3aa8-3c74, 5f08-5fb2 | T: since 2026-10-31 set-7 records with raw kind 7 spawn as actor 2 (raw 1/3/9/10 skipped), Birdhead.rsrc imported, SHAP flag 0x0400 unpacked (LZSS); generation points too (6:3be0, a5-0x5280[7] = 2); any birdhead-specific rule P | combat, combat_art, render_opening / test_temple_arrival, test_shape_lz; [plan](research/temple-implementation-plan.md) |
| Window escape and glass timeline | 2:5d56; CODE:23; DATA/SEQS | T: isolated opening with glass cue | opening_animation, audio / test_opening_animation, test_audio_integration |
| Opening story, title and audio synchronization | 15:45c2/4ee8/6f1a/6fec; CODE:16 SCRP; NIS/Title archives | T: recovered coordinator calls, native scene/audio program; pixel parity P | intro, extract_intro / test_intro, test_extract_intro, test_intro_scene |
| Title cloud composition, initial fade and finite playback | 15:7014-7060/7178-7224; 16:0366-0468/14be-14d4; Title SCRP:25004 | T: signed rear-cloud coordinates and original scene deadlines; QoL: continuous cloud motion through both fades, verified seamless script repetition | intro / test_intro, test_intro_scene.OriginalTitleTests |
| Story lettering baselines and three horizontal shadow/color passes | 15:0302-03ae/2976-2982; 17:0694/0b40-0b4c/294e-29ba/28de/2b9a; FOND:213/NFNT:24878 | T: ordinary intro subtitle layout, leading-space skipping, decorative-initial origin and reserved display black at index 255 | intro / test_intro |
| Two-pass 2x1-pixel dissolve and cached group order | 15:2d7a/31ba-3256; Prince2.opt DSLV | T/A: per-group alternating word offsets verified against native CPU writes; original cached permutation, deterministic fallback when cache absent, native Random seed P | intro, extract_intro / test_intro, test_extract_intro |
| Visible 510x384 rectangle and host presentation | 17:1ada-1b00; NIS SHAP:25001 | T: native extent, cropped host padding, nearest-neighbor fitting and inverse pointer mapping | game_ui, window_controls / test_game_ui, test_development_menu |
| Prince environment palette | 3:5f1c-5f44; LEVL:2186; Kid CTBL:25001-25006 | T: palette 25000 + environment kind, independent of SHPL/FRAM bank; rooftop CTBL 25005 | render_opening, scene_prototype / test_palettes, test_game_ui |
| CUST full-room background and foreground | 3:1378/142a/2324; CUST:4350 | T: fixed level-1 descent-room images and draw passes; animated custom templates P | render_opening / test_harbor |
| Cavern/ruins CUST foreground across dirty cells | 3:239e-23b2/2438; CUST pass1 | T: custom mask is not restricted to clean-cut caller (9,0); level-five room-three pillar/ascent leaks fixed;30 native dirty-cell command comparisons, shared raster decoder | caverns / test_cavern_custom_foreground; probe_carpet_room_repaint_music |
| Harbor floor, pillars and waves | 23:0248, 0d1c/0dce; DATA:cc32/cc3a | T: native SHAP/PIEC offsets, phase cycle and wave clip rectangles; native random phase seeding / conditional redraw P | render_opening, harbor / test_harbor |
| Ship activation, two-pixel drift and departure limit | 2:5374; 23:1066/1120/1256 | T: level-1 counter, entry-pose reset and original SHAP layers; full native obstacle-bank lifecycle P | harbor, render_opening / test_harbor |
| Ship catch, grip movement and boarding sequence | 23:12ba/12f0/132c; SEQS:59 | T: strict X/row/time bounds, relative movement and complete original pose chain | harbor, terrain, scene_prototype / test_harbor |
| Water entry, splash and delayed death; harbor exception at Y=730 | 23:06fe/0b3e; 4:36ae-36ec | T: player/NPC thresholds, exemptions, six splash poses and eight-frame death delay; host stores one splash per actor rather than the native shared slot | harbor, terrain, scene_prototype / test_harbor |
| Boarding requests level transition (-16), then holds invisible pose | 4:2f2c; 6:5022; SEQS:59/215 | T/A: original request and sequence translated; host completion screen substitutes for the unported movie / next-level loader | sequence_runtime, scene_prototype / test_harbor |
| Dynamic tiles/gates, ceilings, other levels and full level-transition pipeline | remaining level/controller routines | P | not yet ported |
| Dead-pose counter, any-key retry and centered restart message | 2:47e6/7148; 4:3b88/47a0; 3:433a | T: ordinary dead-pose/key gate and actual current/pending playback completion; frontend timeout P | rebirth, audio, scene_prototype, window_controls / test_rebirth, test_audio |
| Audio cue arbitration, source samples and rooftop music pool | CODE:5; DATA; INST/snd; MIDISnd/DigiSnd | T/A: ordinary level-1 subset; original instruments with host sampler, not bit-exact Mac MIDI driver | audio, audio_formats, extract_audio / test_audio, test_extract_audio, test_audio_integration |
| Carpet chamber theme lifetime | 8:0d50/0d5c/14f0/14ae; 5:5252/550c; RugRoom MIDI | T: entry requests114 once, completion permits normal cavern ambient, leave stops specifically114, re-entry requests it again, sitting replaces with115/116;96 native admission fixtures; host ambient toggle classification retained | environments, audio / test_carpet_room_music, test_audio; probe_carpet_room_repaint_music |
| LEVL checkpoint trigger and restored start | LEVL:39a6; 2:6b46/1674/19ba/5d50 | T: level-1 foot/cell trigger, native anchor, facing/full life and opponent/generator snapshot; host cavern-mechanism snapshot tested through level-5 Alt+R and progress saves; full native normalization/story pipeline P | rebirth, scene_prototype / test_rebirth, test_level5_retry |
| F3 screen jumps seed the latest route checkpoint from LEVL | host feature | T: route order rather than slot order; earlier/secret jumps and New Game clear it; not an original activation rule | scene_prototype / test_rebirth |
| F3 cavern entries avoid sealed decorative floor pockets | host feature | T: room-link-connected space, stable terrain fallback, live gate state and lower-floor Room 21 preference; placement heuristic only, not gameplay pathfinding | development_entry, scene_prototype / test_development_entry, test_caverns |
| F3 stitched level map | host feature | T: compact Open map entry, separate unframed workspace, nested Back/Escape and level arrows, real room links, initial enemy bones, safe teleport and return to the room before death/restart, spatial keys, persistent lossless artwork cache, aspect-preserving HD presentation, two-size cache and partial Tk hover uploads without world redraw | development_map, preview_cache, game_ui, window_controls / test_development_map, test_preview_cache, test_development_menu; [details](DEVELOPMENT_MAP.md) |
| F3 visual playback gallery | host feature | T: imported sequence groups, native snapshots for every part, private silent scene players, cached previews, six-part pages, direct seek, arrows/wheel, hover and high-resolution partial uploads, nested Back/Escape and pause/key-repeat protection | playback_preview, preview_cache, game_ui, window_controls / test_playback_preview, test_attract_scene; [details](PLAYBACK_GALLERY.md) |
| In-game F3 menu, peaceful scene, ordinary-key pause resume, Windows fullscreen | host features | T: tabless tools hub and separate Playback page with optional debug bar, attract-cycle level-control exclusion, sample-offset seeking, centered cutscene pause, modifier/media/navigation/system-shortcut exclusions, held-key consumption and focus reset; not recovered Mac gameplay rules | window_controls/game_ui / test_game_ui, test_development_menu, test_attract_scene |

## Corpse Visibility

The former guard-only visibility exception could leave either a small strip
above the parapet or a whole flat corpse exposed over a sloping edge.
Settled Prince and ordinary guard corpses now follow the explicit native
IsCharNonViewable rule, including guard pose 228. This changes drawing only:
death sequences, coordinates and stored NPC records remain intact.

## Next Recovery Pass

Temple research: [actor-to-plate lifetime](research/temple-actor-plate-lifetime.md)
records R (not runtime-integrated) CheckPress through ordinary/permanent
pressure, rock-only activation and plate release:540 persistent traces and
7,110 native/reference comparisons,10 asset-free regressions. This extends
the separate16,461-case [admission probe](research/temple-pressure-admission.md)
within its stated scope. Supporting-cell/actor/FRAM inputs, call schedule,
audio/redraw remain supplied; full FrameAdv and actual support/contact remain P.

The subsequent [mixed-lifetime trace](research/temple-mixed-lifetime.md)
extends R to both original level11 gate/rock chains and source/target TROB
iteration/compaction:120 persistent traces/14,784 native comparisons. Separate
[gate steps](research/temple-gate-animation.md) cover41 original anchors/6,300
cases, and [permanent setup](research/temple-permanent-pressure.md) covers68
plate markers/1,304 cases. These remain research, not runtime integration;
rock movement, real contact/support, full FrameAdv and saves/reset remain P.

[Real gate services](research/temple-gate-services.md) corrects the initial
LoadKid/relief labels and adds11,361 native comparisons.4:4b02 copies the
saved Prince, not support caches;5:4766 is level4 relief, not crushing;
a5-0x5008 is its sigh countdown, not damage.3,075 connected temple gate steps
execute both real bodies, with only sound/redraw supplied. Earlier gate/mixed
v2 reports preserve their transition counts and correct those semantic names.
The real callees also pass inside the120 persistent mixed traces/14,784
comparisons; working-actor copies are checked while actor/FRAM inputs remain
explicitly resupplied per operation. [Mixed rock motion](research/temple-mixed-rock-motion.md)
now extends R to real geometry/motion/crush admission and both bank lifetimes:
192 traces/83,040 comparisons, explicitly no actor contact. Actor consequences,
presentation and full FrameAdv in that composition remain P.

[Hanging gate helpers](research/temple-gate-hanging.md) add14,268 comparisons
for native StopGate, JumpSeq47 selection/copyback and separate sound29
admission at all41 original anchors. Supplied type0 actors/resource existence;
no clip execution, full caller schedule or mixed hanging/contact integration.
[Connected hanging animation](research/temple-gate-hanging-animation.md)
adds26,568 comparisons through the real type4 body for six supplied states;
ordinary/fast/permanent actor effects and cue/redraw order are distinguished.
Actor animation and full bank/frame scheduling remain P.

[Actor clip progression](research/temple-gate-actor-clip.md) extends R through
native AnimChar and original SEQS47/2/9/210 bytes:2,952 persistent traces,
73,800 comparisons and9 asset-free regressions. Selection precedes the
mode5/X+16/three-pose transition and active2/mode0 link; selected source47
persists. Actor-update/copyback scheduling and handles are supplied; no
physical fall/contact/death or full FrameAdv/bank iteration claim.

[Actor/gate bank progression](research/temple-gate-actor-bank.md) extends R
through full native AnimTrobs iteration/compaction interleaved with actor
clips:2,460 persistent traces/78,720 comparisons,8 asset-free tests. Complete
bank bytes/order and actor effects pass in both supplied schedules, with
different first-cycle results. Original FrameAdv order, reachable supplied
banks/placements and physical fall/contact/death remain P.

[World/Prince callers](research/temple-world-prince.md) extend R through
actual2:6224/62e6, native gate-bank/clip/gravity and actor save2:6472:
8,528 traces/34,112 world comparisons plus2,400 direct gravity controls,
12 asset-free regressions. PlayerCtrl, geometry/contact/hazards, opponent
and presentation/clock services are supplied. Outer FrameAdv, real controls,
reachable placements, physical consequences and playable temple remain P.

[Hanging controls](research/temple-hanging-control.md) extend R through native
GenCtrl6:0560's bounded unarmed/living type0 route and6:18e0/1998/1a84/1b7e,
native predicates/ClearControls/JumpSeq and first clip after gate selection:
28,220 traces/112,880 operation comparisons,14 asset-free regressions.
Preview effects survive partial sequence-state restoration. Cell/bars values,
latches and the four-call schedule are supplied; actual PlayerCtrl and
physical support/contact/fall in the real coordinator remain P.

[PlayerCtrl in the world caller](research/temple-player-control.md) extends R
through actual4:3b88/3cae preparation, latch restore/normalization/orientation/
cooldown/save and hanging GenCtrl inside2:6224/62e6:7,090 single-world-update
comparisons,16 asset-free regressions. Sixteen previews retain actor effects
through actual2:6472. Sampled axes, cell/bars responses and other geometry/
contact services are supplied; physical input, outer FrameAdv, death branches,
reachable multi-frame gameplay and playable temple remain P.

[Real controller geometry](research/temple-controller-geometry.md) extends R
through actual current/front/above ReadCell/cache and SlideRockInCell10:2036
inside world/Prince/PlayerCtrl:9,534 world comparisons plus8,064 direct
query/returned-edge comparisons,15 asset-free regressions. Corrects `bars`
as a legacy supplied alias for sliding-rock occupancy; native left-edge
clipping raises with `max`. Initial actor anchors/widths/static banks and
input samples are supplied. Real frame/foot geometry, other physical contact,
persistent gameplay and playable temple remain P.

[Prince frame support](research/temple-kid-frames.md) extends R through type0
LoadFrame4:2a72/2a8e, original Kid FRAM/AFRM and signed supporting-column
calculation:22,528 comparisons,8 asset-free regressions. Prepared bindings,
poses and X inputs supplied. Sprite bounds/width, foot Y/row, real controller
composition and reachable physical frame progression remain P in this block.

[Frames in world control](research/temple-frame-progression.md) extends R to
real Kid LoadFrame inside actual world/PlayerCtrl/cell queries, then bounded
AnimChar/LoadFrame continuation:23,964 comparisons,9 asset-free regressions.
Script X/Y/row and supporting columns are recovered in this domain, not
physical support/climb reachability. Continuation order, initial anchors,
frame width, sampled inputs and other contact/services remain supplied;
outer FrameAdv and playable temple remain P.

[Prince sprite bounds](research/temple-sprite-bounds.md) extends R through
type0 LoadFrame/SetupSword/GetCharEdges, sword extent and edge rows/columns:
33,792 comparisons,10 asset-free regressions. Dimensions from original Kid
SHAP headers and rectangle intersection/library bindings remain supplied;
resource loading/rasterization, connected world contact and physical
reachability/full FrameAdv remain P.

[Sprite bounds in world control](research/temple-world-bounds.md) extends R
through real LoadFrame/SetupSword/GetCharEdges inside world/PlayerCtrl and
static rock queries:8,856 comparisons,6 asset-free regressions. Final saved
actor rectangles/edges are derived; supplied fixed18 width would change18
selected animations. SHAP-size/graphics services, input/placement/static
banks and remaining physical contact/floor/hazards stay supplied; repeated
physical frames, outer FrameAdv and playable temple remain P.

[Gate admission](research/temple-gate-admission.md) extends R through4:5b0e:
102,400 controlled direct comparisons and14,080 predicate comparisons after
2,816 real Kid bound chains,8 asset-free regressions. Visible height, exact
thresholds, exemptions and signed wrapping are checked; graphics services
stay supplied. Real contact/barrier callers and physical reachability remain P.

[Standing clearance](research/temple-gate-standing.md) extends R through
GateBarrToStandUp4:5baa and actual cell/neighbor traversal:39,318 comparisons,
11 asset-free regressions, no supplied services. First-gate priority,
inclusive native-X band, cached normalized column and room-base-pointer
side effects are checked. Standing callers/animation, full contact and
multi-frame physical reachability remain P.

[Gate contact routing](research/temple-gate-contact.md) extends R through
CheckGateForKid4:60e4, real cells/admission, JumpSeq50 and contact marking:
61,382 comparisons,14 asset-free regressions. ALIVE/HP, lookup priority,
exact overlap and failed resource behavior are distinguished. Distance,
overlap construction and terminal ejection/cave responses remain supplied;
subsequent damage/death, full collision/world physics and playable temple P.

[Unarmed airborne collision response](research/temple-air-collision.md) extends
R through the isolated type0 branch of4:589e, with real alignment, relative
movement, original46/47/121 animation and Kid frame reload. All9,648 controlled
native calls match; signed velocity49/50, ALIVE/health separation, pose-specific
word+24 clear and missing-resource continuation are pinned. Actor/admission
and resource handles remain supplied. Armed reactions and wall spacing are
separately recovered below; body/contact construction, complete caller
composition and playable temple remain P.

[Armed airborne response](research/temple-armed-collision.md) extends R through
the isolated type0 armed branch, including real static-rock lookup/strike
predicate, relative reaction, original64/65/93 slices and Kid reload:12,456
native calls match. Gate low-byte60/61, active/source distinction, mark/audio
requests and disarming are pinned. Contact/cache/MOB bank/frame width and
resource/audio endpoints remain supplied; wall spacing is recovered separately
below. Body construction, moving-rock/full-frame composition and playable temple
remain P.

[Post-response wall spacing](research/temple-wall-spacing.md) extends R through
isolated4:3982: real metadata-derived point/distance, adjacent-cell/wall decision,
relative movement, Kid reload and current-cell refresh. All27,364 calls match,
including1,345 wall-kind anchors across levels10–13, original Kid poses, cache
controls and17/18/19 boundaries. Word+52/type11 and room3/environment6 exceptions
are distinguished; non-temple undefined-cell behavior is excluded. Metadata and
admission remain supplied; caller/body/complete physical-frame composition and
playable temple remain P.

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
`tools/probe_input_bank.py` compares a separate executable bank model with
14,265 actual original sample/reset/save/remap cases, without external service
stubs. Raw axes are supplied after ReadKeyboard; full action dispatch and
FrameAdv are excluded. The formerly expected-failure regressions now pass:
early jump taps clear at pose 26, horizontal crouch-rise requests clear in
mode 5, released Ctrl cancels a pending counter, and Shift + Backward uses
the voluntary turn. The full native latch lifecycle still needs integration,
without changing established animation clocks or intentional tolerances.

The [unarmed routing extension](INPUT_RECOVERY.md#executable-unarmed-routing-2026-10-27)
adds 17,415 original dispatch comparisons and 36 persistent sampled steps, all
matching an independent reference. Standing/run/start/turn/preparation priorities
and router-owned resets are recovered; action bodies, OS polling, full animation
and FrameAdv remain outside that matrix. A separate 7,290-call DoStrike matrix
verifies actual modifier/direction consumption, supplying JumpSeq without
executing attack animation or outer armed admission. The production Ctrl modifier is also
checked against 10,935 native samples. The user revoked the former running
stop-and-draw QoL: runtime draw now requires fresh/held Ctrl at a standing gate,
and released taps preserve normal running-jump/braking traces. This bounded
modifier integration does not replace the host's directional command slot.

[Ordinary action consumption](research/input-action-consumption.md) executes
the action bodies beyond the router sinks: 11,304 comparisons for run/restart,
turn, cautious step, standing forward jump and running jump. All match an
independent reference, including full bank effects, original relative-X word
arithmetic and warnings. Terrain services and animation requests remain supplied;
pose advancement, outer scheduling and whole runtime queue migration remain P.

[Composed input traces](research/input-controller-traces.md) match 45,044
native router-plus-action cases and 62 persistent sampled steps in 18 traces;
1,936 unsupported-action cases are explicitly excluded. Sampling/remapping,
action consumption and X/warning persistence execute together. Terrain and
pose/mode/facing contexts remain supplied, JumpSeq is a request sink, and
animation/physics/full player-wrapper/FrameAdv parity remains P. A local
host conflict experiment did not demonstrate a visible extra action; the
architecture mismatch must not be mistaken for a reproduced user bug.

[Saved player-input wrapper](research/player-input-wrapper.md) adds 67,850
matching cases/steps through actual 4:3cae-3d14 plus the covered sampler/router/
actions, excluding 740 unsupported-action cases. It checks saved versus working
bank ownership, raw-direction gate, recording order/result, countdown and
persistent state despite a different working bank between calls. Keyboard,
recording and terrain endpoints remain supplied. Death/replay/inversion,
uncovered action families, animation/physics/FrameAdv and runtime migration P.

[Low/prone input consumption](research/low-input-consumption.md) adds 76,357
matching original calls/steps, including 100 persistent saved-player steps in
32 traces. Actual JumpSeq selection/cursor writes replace the request sink
for these paths. Crouch/rise/crawl resets, direction consumption, resource
failure and no-gap ordinary Down entry are checked; geometry/pickup/carpet
decisions and pose/mode progression remain supplied. A concrete Shift+Forward
crouch classification mismatch is corrected in the scene. Full native-bank
runtime migration, other controller families and FrameAdv remain P.

[First directional-bank runtime stage](research/directional-bank-runtime.md)
uses a production bank for deferred standing turns/cautious steps and their
ready gates. Direct native comparisons verify production sampling, clearing,
remapping and bounded standing selection in 42,120 cases. Scene regressions
cover independent Up/Down, current modifier/facing choice, consumed versus
fresh horizontal release, host repeat policies and interruption clearing.
Airborne/low/ledge/armed family migration and whole-frame parity remain P;
the old command slot is bypassed only while the new family owns input.
Another 810 original Up-choice/DoJumpUp-prefix cases confirm dispatch from
the current Forward latch and the vertical prefix's direction clearing/Up
consumption, stopping before terrain lookup. Total 42,930 matching cases.

The second stage extends that owner through grounded run start/cycles,
drift, running turn and brake. The old grounded dispatchers are bypassed or
removed together. Another 12,960 direct production/native GenCtrl cases
match, including startup, run priorities/common consumption, drift and
protected clears. Real scene tests cover geometry-rejected Up remaining
pending, conflicting Up/Down, braking before wall alignment and Ctrl draw
admission. Host initial chord/held-repeat/vertical-climb tolerances stay
explicit; the sequence-4 airborne reset/return policy remains a boundary,
not proof of whole saved-bank continuity or FrameAdv parity.
