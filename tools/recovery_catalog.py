"""Index known original routines without treating disassembly as recovered logic."""

import argparse
from collections import Counter
import csv
import io
from pathlib import Path

from pop2.paths import PROJECT_DIR


CATALOG = PROJECT_DIR / "docs" / "RECOVERY_CATALOG.csv"

# These reviews cover specific ordinary branches, never an entire routine.
REVIEWS = {
    (4, "AdjustRoom"): ("partial", "tools/probe_temple_gate_distance.py", "temple gate distance calls: displayed room precedence, supplied left/right slot adjustment and signed wrapping; InitRoom slot construction excluded"),
    (4, "GetBarrDistFromFace"): ("partial", "tools/probe_temple_gate_distance.py", "environment2 ordinary gate type1 with actual admission/classification/AdjustRoom;79104 face/back calls total, no endpoint stubs; body and room slots supplied; other barriers/general distance selector excluded"),
    (4, "GetBarrDistFromBack"): ("partial", "tools/probe_temple_gate_distance.py", "environment2 ordinary gate type1; back distance computes even when face admission returns-1; whole A5 side effects checked; sprite bounds/InitRoom/full collision excluded"),
    (4, "GetUndefineCellId"): ("partial", "pop2/terrain.py;tools/probe_cliff_void.py", "ordinary undefined cells in levels 3-9: rooftop air, level-six room27 and level-nine room16 exterior air, other cavern/ruins boundaries solid; 8800 native comparisons; special top-row flag and environment2/6 branches not translated here"),
    (15, "NISThroneRoom"): ("partial", "tools/extract_intro.py;pop2/intro.py;pop2/scene_prototype.py", "NIS 6 exported per facing with ThroneNIS/Kid/Prince/Ruins shapes, text panel and Prince-relative drawing; screen before it approximated by 15:6d46; area dissolve order not native"),
    (15, "DrawDeadKid"): ("partial", "tools/extract_intro.py;pop2/intro.py", "Kid SHAP 25081 at the Prince's X/Y (mirrored facing right), sword SHAP 1011, CTBL 1004 at 240"),
    (15, "QueenAddNIS"): ("partial", "tools/extract_intro.py", "environment 4 only: Ruins SHAP 4200-4207 throne room redraw and DrawDeadKid(1)"),
    (15, "Discovery"): ("partial", "tools/extract_intro.py;pop2/intro.py;docs/LEVEL4_RECOVERY.md", "original coordinator exported to portable operations and level 3-to-4 host wiring; three callback-free flags-6 animations; native host stall parity omitted"),
    (16, "runScript__10tAnimationFiUs"): ("partial", "pop2/intro.py;tools/extract_intro.py", "12 Discovery/tree scripts and 481 native incremental steps; carried layers/events/interval/end checked; tree callbacks and maintain cadence not executed"),
    (16, "draw__10tAnimationFv"): ("partial", "tools/extract_intro.py", "69 Discovery frames and 144 native drawing calls agree in order/coordinates/flags; shape dimensions supplied, not independent pixel rasterization"),
    (16, "setPos__10tAnimationFii"): ("partial", "tools/extract_intro.py", "Discovery absolute origin replaces ANI bounds origin; original execution with supplied OffsetRect; other animation uses omitted"),
    (16, "PlayTheAnimation"): ("partial", "tools/extract_intro.py;pop2/intro.py", "Discovery flags 6/no callback/no background fill only; portable nominal intervals, no Macintosh event-loop or stall parity; other modes fail explicitly"),
    (3, "CheckGateInFore"): ("partial", "pop2/caverns.py;pop2/scene_prototype.py", "ordinary moving-gate body masks by physical row, supporting column and mode; 80 native admission checks; full NPC-bank and special crush redraw paths partial"),
    (4, "IsLedge"): ("partial", "pop2/terrain.py", "ordinary empty/floor catch geometry and left-facing phase-zero gate veto (512 native gate checks); DoJumpUp gate override retained; special floor branches partial"),
    (2, "ReadKeyboard"): ("partial", "pop2/mac_input.py", "ordinary keyboard priority"),
    (2, "CheckAlert"): ("partial", "pop2/rebirth.py;pop2/scene_prototype.py;tools/probe_ruins_hud_exit.py", "marker at 6b46: checkpoint admission prefix, level8 room9 requires sword type1 (80 native checks); full record save excluded"),
    (2, "ResetFrameVars"): ("partial", "pop2/scene_prototype.py", "five/six-tick cadence only"),
    (2, "SaveRebirthPtStatus"): ("partial", "pop2/rebirth.py;pop2/scene_prototype.py", "level-1 opponent/generator snapshot; dynamic normalization and story state missing"),
    (2, "SetRebirthPtInitials"): ("partial", "pop2/rebirth.py;pop2/scene_prototype.py", "level-1 checkpoint room/cell, facing, full maximum life and idle startup"),
    (3, "DrawRestartMessage"): ("partial", "pop2/scene_prototype.py", "original text/font centered in HUD, reference palette-index-6 displayed color; native frontend timeout missing"),
    (4, "PlayerCtrl"): ("partial", "pop2/rebirth.py;pop2/scene_prototype.py;pop2/audio.py", "ordinary dead-pose counter/retry gate with current/pending SDL audio completion"),
    (4, "IsDeadPos"): ("partial", "pop2/rebirth.py", "Prince dead-pose IDs only"),
    (4, "GateBarrToStandUp"): ("partial", "pop2/terrain.py;pop2/scene_prototype.py", "cavern phase 1-183 directional crouch-rise veto; 4096 native checks; other environments omitted"),
    (4, "CheckGateForKid"): ("partial", "pop2/terrain.py;pop2/scene_prototype.py", "cavern Prince consecutive overlap, forced crouch, nearest-side ejection and SEQS 118 crushing; 1920 native selection/displacement/damage checks with supplied masks"),
    (5, "AddKidDeathSong"): ("partial", "pop2/rebirth.py;pop2/audio.py;tools/extract_audio.py", "extracted death-method mapping, level-1 songs and actual playback completion"),
    (5, "AddSound"): ("partial", "pop2/audio.py;tools/extract_audio.py", "extracted cue priorities, pending arbitration and ordinary actor footstep suppression"),
    (5, "CheckSquishedFingers"): ("partial", "pop2/pressure_plates.py", "same-room modes 2/6 and supporting-foot linear-cell admission; cue 29 at slow/fast closure without damage; 9600 native comparisons; copied actor bank replaced by explicit state"),
    (5, "CheckPress"): ("partial", "pop2/loose_floors.py;pop2/pressure_plates.py", "supporting-foot and pose/mode/height admission for loose floors, immediate ruins type15 shelves including ceiling pose79, and pressure plates; special actor host incomplete"),
    (5, "ATMSpikes"): ("partial", "pop2/wall_spikes.py", "cavern visible-room/left-neighbor MOB lifetime, retract/hold phases and cues 282/284; 256 native phase updates; shared MOB bank incomplete"),
    (5, "DrawObjSpikes"): ("partial", "pop2/wall_spikes.py;pop2/caverns.py;pop2/level_rendering.py", "cavern back/front and blood banks, DATA offsets and masked transfer; all 18 representative native draw commands matched; other environments omitted"),
    (5, "MobSpikes"): ("partial", "pop2/wall_spikes.py;pop2/scene_prototype.py", "outward phase 1/2 hit admission; native Prince trigger/hit/sequence/alignment comparisons over 23400 supplied-bound cases; temple/special actors omitted"),
    (5, "TriggerSpikes"): ("partial", "pop2/wall_spikes.py;pop2/scene_prototype.py", "cavern idle activation and held-pose renewal, shared MOB capacity not unified with other hazards"),
    (4, "GetBarrCode"): ("partial", "pop2/terrain.py;pop2/scene_prototype.py", "wall-spike type 3 reserved for explicit DoStepFwd query; run startup and ordinary collision keep type 4; native close-start clearances 39/17 verified; other barrier special cases partial"),
    (5, "PushPlate"): ("partial", "pop2/pressure_plates.py", "link timer, depression after chain traversal, ordinary/permanent press and click cue; level-three reverse plates integrated"),
    (5, "Trigger"): ("partial", "pop2/pressure_plates.py", "native linked target traversal; level-three stone gates, exits and all nine projectile traps dispatched"),
    (5, "TriggerGate"): ("partial", "pop2/pressure_plates.py", "level-three reverse-plate dispatch; special level/story and closing-on-actor branches missing"),
    (5, "TriggerObject"): ("partial", "pop2/pressure_plates.py;pop2/darts.py;pop2/environments.py", "closed exits and fresh-plate idle-shooter admission; level8 non-entrance exits require sword type1 (300 native admission checks); other environment branches partial"),
    (5, "CloseExit"): ("partial", "pop2/cavern_state.py;tools/extract_caverns.py", "native first-room 79/47/0 closure retained separately from pressure-driven exit opening"),
    (5, "GetLinkNext"): ("partial", "pop2/pressure_plates.py", "signed next index from native ten-byte link records"),
    (5, "GetLinkTimer"): ("partial", "pop2/pressure_plates.py", "native initial timer with portable session override"),
    (5, "ChangeLinkTimer"): ("partial", "pop2/pressure_plates.py", "portable timer mutation; no Macintosh handle storage"),
    (5, "GetLinkCell"): ("partial", "pop2/pressure_plates.py", "native signed target cell and unassigned-link sentinel"),
    (5, "GetLinkRoom"): ("partial", "pop2/pressure_plates.py", "native one-based target room converted at the terrain boundary"),
    (8, "DrawCaveGateMovable"): ("partial", "pop2/caverns.py;tools/extract_pressure_plates.py;docs/CAVERN_RECOVERY.md", "native two-layer shapes and quarter-phase displacement; historical 636 individual and 504 combined clean/floor/climb comparisons; front cap now preserved above ordinary dirty-cell clip during motion"),
    (5, "ComputeClipRect"): ("partial", "tools/probe_gate_repaint_clip.py;pop2/caverns.py;docs/CAVERN_RECOVERY.md", "90 native row/column/viewport checks using original DATA; ordinary flag-zero cell bounds only; supplied SectRect, not native dirty admission/rasterization or special row-zero flag"),
    (8, "DrawCaveExitMovable"): ("partial", "pop2/caverns.py;tools/extract_pressure_plates.py", "level-three exit body, pixel-phase displacement and native clips; 226 room/floor/climb command-list comparisons; special actor draw pipeline incomplete"),
    (8, "TriggerGateWithRevPlate"): ("partial", "pop2/pressure_plates.py", "fresh versus held reverse plates, opening/fast close and debris permanence; 17280 native controller updates across all 16 gate buttons"),
    (8, "CaveMoveSquishingGate"): ("partial", "pop2/pressure_plates.py;pop2/scene_prototype.py", "nearby Prince SEQS 118 poses 264-266, narrower linear-cell contact and mode-3 final slam to 48 with cues 20/18; 576 original plus 480 additional native gate updates; other actor modes omitted"),
    (8, "DrawCaveDart"): ("partial", "pop2/caverns.py;tools/extract_pressure_plates.py", "native mouth shapes and dimension-dependent clips; 315 whole room/floor/climb drawing-list comparisons for all nine shooters"),
    (8, "MobDart"): ("partial", "pop2/darts.py;pop2/scene_prototype.py", "native diagonal velocity, ceiling/wall/gate collision and incoming neighbor rebasing; 3240 controller/projectile updates matched across all nine traps; shared MOB bank incomplete"),
    (8, "CheckDartHit"): ("partial", "pop2/darts.py;pop2/scene_prototype.py", "rectangle/swept contact, SEQS 79 exemption, one-life wound and ordinary fatal response; 14280 native hit comparisons; special actors and cross-hazard pending damage incomplete"),
    (5, "AddSong"): ("partial", "pop2/audio.py", "first pending song retained per update"),
    (3, "GetFlaskBubbleColor"): ("partial", "pop2/caverns.py", "level-three normal/mega body and two mirrored monochrome particle layers; all 196 native phase/room layers pixel matched; other environments incomplete"),
    (3, "LoadFlaskSet"): ("partial", "pop2/caverns.py", "original Prince SHPL 3000 and CTBL relocation to indices 224-238; verified native RemapCTBL; full handle pipeline omitted"),
    (5, "TriggerFlask"): ("partial", "pop2/potions.py;pop2/game_session.py", "initial phase Rnd(26)+1, original 28-update visible flask cycle; native Trob bank replaced"),
    (6, "TryPickUp"): ("partial", "pop2/potions.py;pop2/scene_prototype.py", "current/forward flask and sword admission; 644 flask cases plus2200 sword reach comparisons and3520 held-Shift gate calls; complete GenCtrl and special pickup effects not certified"),
    (6, "PickItUp"): ("partial", "pop2/potions.py;pop2/scene_prototype.py", "ordinary standing/crouched alignment, SEQS 50/78, native late effect event and healing/capacity cap; other object types omitted"),
    (4, "RemoveObj"): ("partial", "pop2/potions.py;pop2/terrain.py", "level-three potion removal to floor 1 retaining foreground 0x0f00 decoration; other environments/story objects omitted"),
    (16, "PlaySound"): ("reference-only", "pop2/audio.py", "native Mac driver playback replaced by SDL; full handle pipeline not translated"),
    (5, "SetCueSnd"): ("partial", "pop2/audio.py", "mode 0/1/2 interruption and priority gates"),
    (5, "PlayAmbient"): ("partial", "pop2/audio.py;tools/extract_audio.py", "level-1 bank, inclusive RoofA-D pool and advance-on-repeat; later combat transitions missing"),
    (5, "AddKidScream"): ("partial", "pop2/terrain.py", "ordinary rooftop Prince long fall and harbor room exclusions"),
    (3, "ComputeHalfRect"): ("partial", "pop2/render_opening.py", "climb 135-144 rectangle table"),
    (3, "LoadCustomRoomData"): ("partial", "pop2/render_opening.py", "CUST:4350 fixed descent-room image records only"),
    (3, "LoadCustomRoomShapes"): ("partial", "pop2/render_opening.py", "fixed descent-room SHAP images; animated templates missing"),
    (3, "DrawCustomRoomImgs"): ("partial", "pop2/render_opening.py", "CUST:4350 static background/foreground passes"),
    (3, "DrawKidMeter"): ("partial", "pop2/combat_art.py", "ordinary health icons; upgrade effects missing"),
    (3, "DrawOppMeter"): ("partial", "pop2/combat_art.py;pop2/combat.py;tools/probe_ruins_hud_exit.py", "ordinary icons and head half-points (60 native positive-HP shape/position loops); nearest active-head HUD handoff; no level5 bridge-skeleton meter; native redraw cache and rasterization excluded"),
    (4, "EnGarde"): ("partial", "pop2/combat.py", "ordinary range/pose decisions, selected retreat/turn history, far-run anticipation limits and pursuit; level-5 bridge engage/hold sites 4:0a3a/0aec/0bdc read and ported; special actors missing"),
    (8, "BridgeCheckBreak"): ("partial", "pop2/bridge.py;pop2/scene_prototype.py", "break counter, column 3-7 collapse, Prince SEQS 85 stop, room-7 gate side effect (8:020a-0236); plank wobble 8:06d8 not drawn"),
    (8, "BridgeGetCharCol"): ("partial", "pop2/bridge.py", "rooms 7/12 continue room 10's columns"),
    (8, "IsBrgGateOpen"): ("partial", "pop2/skeleton.py;pop2/combat.py", "body at 8:033c is the bridge guard (turn back, brake, run, SEQS 60); gate test 8:0458"),
    (8, "TriggerBrgFloorMob"): ("partial", "pop2/bridge.py;pop2/caverns.py", "hanging/falling plank choice and emptied custom cells; native redraws at each collapse stage compared"),
    (8, "DrawObjBrgFloor"): ("partial", "pop2/bridge.py;pop2/caverns.py", "CUST plank shape at column X with sag and frame offsets"),
    (8, "DrawCarpet"): ("partial", "pop2/caverns.py;pop2/carpet.py", "unused carpet SHAP 25312 at X 149, bottom 363; emulator capture matched"),
    (8, "SetupCarpet"): ("partial", "pop2/carpet.py;pop2/caverns.py", "ridden carpet shape/offsets by frame; red fade of entries 45/46 (8:10ba-119c) omitted"),
    (8, "Sitting"): ("partial", "pop2/carpet.py;pop2/scene_prototype.py", "counter start, crash below Y 100 with bars shut, SEQS 129, sound 117, death method 9; MakeSpace of cell 23 not modelled (level ends or Prince dies)"),
    (8, "DrawCaveBars"): ("partial", "pop2/caverns.py;tools/extract_pressure_plates.py", "CUST record phase + 1 (SHAP 4051-4053/4064) as a pressure-drawing record"),
    (5, "TriggerScythe"): ("partial", "pop2/scythes.py;pop2/scene_prototype.py", "5:57bc admission (living, near floor, 28 pixels into the column) and resting-state start; AnimScythe 5:4584 phases 1-19, sounds and blood"),
    (5, "CheckScytheHit"): ("partial", "pop2/scythes.py;pop2/scene_prototype.py", "first scythe cell of columns -1..+1, hit phases and blade rectangles, SEQS 113/190, death method 5, sound 278 and blood; drawing from exported native patches"),
    (5, "GetScytheHitType"): ("partial", "pop2/scythes.py", "phases 2, 16 and 17"),
    (5, "ComputeBladeHitRect"): ("partial", "pop2/scythes.py", "a5-0x372a/-0x3722 rectangles and their union, offset by the cell"),
    (8, "TriggerCaveBars"): ("partial", "pop2/pressure_plates.py", "fresh-press open/close and one phase per update with sounds 282/284"),
    (4, "OpponentClose"): ("partial", "pop2/combat.py", "ordinary close-range decisions"),
    (4, "WaitingEngarde"): ("partial", "pop2/combat.py", "ordinary multi-guard spacing and same-facing pursuit; self-nearest obstacle branch missing"),
    (4, "GenFight"): ("partial", "pop2/combat.py", "102-pixel spacing plus 36 per later nearby NPC, including corpses; full native bank lifecycle missing"),
    (4, "GetCellsInFront"): ("partial", "pop2/combat.py;pop2/terrain.py", "ordinary facing-relative front cells from controller anchor column"),
    (4, "GetDist1"): ("partial", "pop2/coordinates.py;pop2/combat.py;pop2/terrain.py;tools/probe_character_columns.py", "all65536 signed native X values in both facings; mixed word/long subtraction and remainder; original196608-call column/distance audit; caller frame/foot loading excluded"),
    (4, "DoOppTumbleSeq"): ("partial", "pop2/combat.py;pop2/terrain.py", "forced rooftops, generator life flag, death-bank/Rnd(3), overlap and facing/tile vetoes; ordinary rooftop NPCs"),
    (4, "GetOppDeadSeq"): ("partial", "pop2/combat.py", "ordinary rooftop slot-parity corpse 195/228; special actors missing"),
    (4, "AnimChar"): ("partial", "pop2/sequence_runtime.py", "supported opcodes including -14 pickup-effect events and -16 level-transition request; others fail explicitly"),
    (4, "SetKidDeathMethod"): ("partial", "pop2/sequence_runtime.py;pop2/rebirth.py", "SEQS -11 death-music selector for actor 0/1; level-five story branch missing"),
    (8, "DrawCaveLavaBubbles"): ("partial", "pop2/lava.py;pop2/caverns.py;tools/extract_lava.py", "native reference cover/order/death triples compared; enhanced presentation uses continuous original surface"),
    (8, "AnimLava"): ("partial", "pop2/lava.py", "native reference phase/bubble/death branches: 6000 tick comparisons; visual QoL skips ordinary wrap hold without changing deaths"),
    (8, "CheckLavaBoil"): ("partial", "pop2/lava.py;pop2/scene_prototype.py", "supporting-foot column, 43/36 limits, physical row, FRAM bit 0x40 and surface Y; Prince integration only"),
    (8, "GetLavaInfoHnd"): ("partial", "pop2/lava.py;pop2/scene_prototype.py", "native death flags, Rnd(3), facing, SEQS 115/116 and cues 69/70; Prince death host, no Mac handles or skeleton host"),
    (8, "GetLavaCharSeqIdx"): ("partial", "pop2/lava.py", "0x8000 eligibility and 0x6000 sequence-index extraction"),
    (8, "ResetLavaInfo"): ("partial", "pop2/lava.py", "initial cell-modulo-three phase seed, initial bubbles and phase-only cycle reset"),
    (8, "TriggerLava"): ("partial", "pop2/lava.py;tools/extract_caverns.py", "one pool per native tile 23 and visible upper-border copies; native handle/trob bank replaced"),
    (8, "TriggerLavaBubble"): ("partial", "pop2/lava.py", "first inactive bubble reuse, event coordinates/sequence/layer and previous-phase activation"),
    (4, "GetCharCol"): ("partial", "pop2/coordinates.py;pop2/opponent_generation.py;tools/probe_character_columns.py", "all65536 signed native X values agree, including26 old mismatches at word wrap/arguments0..3; actor/foot coordinate choice remains with callers"),
    (4, "GetRow"): ("partial", "pop2/terrain.py", "signed row conversion"),
    (4, "CheckBarr"): ("partial", "pop2/terrain.py;tools/probe_temple_collision_banks.py", "temple4:4e34 history/generated interval/three row sweeps/incoming masks verified26370 native calls; real rock queries/overlays against empty MOB bank, supplied body/previous banks; nonempty rocks/floating ceiling/response excluded"),
    (4, "CheckCollide1"): ("partial", "pop2/terrain.py", "unarmed grounded front-only versus armed front/rear within port sweep"),
    (4, "ClipChar"): ("partial", "pop2/caverns.py;pop2/scene_prototype.py", "cavern ordinary top clipping and Prince exit top/right rectangle; full native clipping pipeline not translated"),
    (4, "IsCharNonViewable"): ("partial", "pop2/render_opening.py", "settled Prince/ordinary guard rooftop corpses except native rooms 15/16/19; guard variant 228 included"),
    (6, "Falling"): ("partial", "pop2/terrain.py;tools/probe_ruins_loose.py", "ordinary falls and grabs, type11/15 slab cushioning;189 native post-impact position/velocity cases; actual level6 mega-potion shaft survives with one HP lost; complete FrameAdv excluded"),
    (6, "HitFloor"): ("partial", "pop2/terrain.py;pop2/lava.py;pop2/scene_prototype.py", "ordinary speed thresholds and sequences; Prince lava-tile landing precedes impact damage and preserves airborne mode (120 native dispatch checks)"),
    (6, "GenCtrl"): ("partial", "pop2/scene_prototype.py;pop2/terrain.py;tools/probe_input_bank.py", "tested locomotion/sword/ledge and cavern Up exit admission/alignment to SEQS:70; ordinary release 11/23/99 with DoJumpHang preview; hard-fall mode-5 reset (72 native checks); live unarmed reset gates (900 native checks), early-jump and horizontal crouch-rise requests cleared; gate climb clearance/SEQS:73 (6144 native checks); full input latches/special levels partial"),
    (6, "StairClimbing"): ("partial", "pop2/scene_prototype.py", "ordinary ledge entry and standing crouch fallback via 1068 only"),
    (6, "DoStepFwd"): ("partial", "pop2/mac_input.py;pop2/terrain.py", "ordinary clearance/caution; dynamic tiles missing"),
    (6, "DoRunJump"): ("partial", "pop2/terrain.py", "ordinary two-cell takeoff alignment"),
    (6, "CheckOppGenPts"): ("partial", "pop2/opponent_generation.py;pop2/combat.py", "tested rooftop reinforcement branches"),
    (6, "IsTimeToGenOpp"): ("partial", "pop2/opponent_generation.py", "ordinary rooftop eligibility and DIVU/SWAP full-word counter gate; full native NPC bank lifecycle missing"),
    (6, "CutAllOpponents"): ("partial", "pop2/combat.py", "horizontal Prince cuts carry ordinary running/jump poses and movement flags; stationary, vertical and special-actor branches missing"),
    (6, "TransferOppInfo"): ("partial", "pop2/combat.py", "ordinary horizontal runner carry, 510-pixel coordinate rebase and persistent actor identity; full native record fields missing"),
    (6, "CutChar"): ("partial", "pop2/terrain.py;tools/probe_ruins_gate_void.py", "horizontal cuts, downward priority and native room-15 right-cut veto; unlinked body threshold and native-room0 continuation with Y-360 (46 native Cut rebases); rooftop/chasm branches separate, full FrameAdv excluded"),
    (7, "SnakeComeOutOfHole"): ("partial", "pop2/ruins_ai.py;tools/probe_ruins_runtime.py;tools/probe_serpent_alert.py", "20000 controller comparisons with supplied alerts;5000 native LOS slice checks include first-obstacle termination and hanging column; full scheduling, actor loading and pose admission excluded"),
    (6, "CheckStab"): ("partial", "pop2/combat.py;pop2/terrain.py", "ordinary contact/damage, type-2 guard death method 14, player/NPC flat alignment, forced and generator-enabled tumbles"),
    (6, "TestStrike"): ("partial", "pop2/combat.py;pop2/scene_prototype.py", "ordinary sword contact, row/strict 15-pixel height gate, no blanket grab/climb immunity; special attacks missing"),
    (6, "GetCharStrikeRanges"): ("partial", "pop2/combat.py", "ordinary Prince/type-2 NPC ranges, facing, sword and engagement flags; special actors missing"),
    (6, "GetOppIdxClosestToKid"): ("partial", "pop2/opponent_selection.py;pop2/combat.py;pop2/ruins_ai.py;tools/probe_ruins_hud_exit.py", "native-ALIVE candidates, vertical 80-unit boundary, serpent fallback, fleeing-head exclusion; 15000 native multi-actor selections plus14961 nearest-on-side checks; complete frame/bank lifecycle partial"),
    (6, "AutoCtrl"): ("partial", "pop2/combat.py", "ordinary unarmed/armed dispatch and shared timer decrement per processed NPC; special actor controllers missing"),
    (6, "OnAlert"): ("partial", "pop2/combat.py;pop2/scene_prototype.py", "ordinary attack/block/advance/retreat gates, counter priority, forced parry recoil and sword lowering"),
    (6, "IsOppGenPtWithTumbleOn"): ("partial", "pop2/opponent_generation.py;pop2/combat.py", "current room packed-life 0x80 flag"),
    (23, "DrawRoofBackWall"): ("partial", "pop2/render_opening.py", "ordinary and harbor background SHAP tables; ordinary fill"),
    (23, "DrawRoofFloor"): ("partial", "pop2/render_opening.py", "floor masks/ledge exceptions; harbor cap offsets, background planks, exposed near-face geometry and partial climb redraw; conditional passes incomplete"),
    (23, "RoofMakeWaterTestRect"): ("partial", "pop2/harbor.py;pop2/scene_prototype.py", "native room-15 offscreen-right death threshold and SEQS:71; sound waits/cinematic/life-drain presentation missing"),
    (23, "DrawRoofLedgeInBack"): ("partial", "pop2/render_opening.py", "row-owned ledge mask subset"),
    (23, "DrawRoofGlass"): ("partial", "pop2/opening_animation.py;pop2/scene_prototype.py", "opening window/glass timeline"),
    (23, "RoofWatchOpps"): ("partial", "pop2/harbor.py;pop2/scene_prototype.py", "harbor water thresholds, exempt sequences and eight-frame death delay; per-actor host splash storage"),
    (23, "SetupSplash"): ("partial", "pop2/harbor.py;pop2/render_opening.py;pop2/audio.py", "six native splash shapes, center/Y offsets and cue 35 playback"),
    (23, "AnimRoofPillar"): ("partial", "pop2/harbor.py", "four-phase wave cycle; native random phase initialization missing"),
    (23, "DrawRoofPillar"): ("partial", "pop2/render_opening.py", "pillar/wave SHAPs, PIEC offsets, DATA clips and ordinary splash occlusion; conditional actor ordering incomplete"),
    (23, "AnimRoofShip"): ("partial", "pop2/harbor.py", "departure counter and two-pixel hull drift; full native obstacle bank missing"),
    (23, "DrawRoofShip"): ("partial", "pop2/render_opening.py", "native body, hatch foreground and wake shapes/offsets"),
    (23, "TriggerRoofShip"): ("partial", "pop2/harbor.py;pop2/scene_prototype.py", "room-entry activation, pose 34-40 reset and counter limits"),
    (23, "RoofClimbingIntoShip"): ("partial", "pop2/harbor.py;pop2/scene_prototype.py", "SEQS:59 selection and ship-relative actor movement"),
    (23, "RoofHangingFromShip"): ("partial", "pop2/harbor.py;pop2/scene_prototype.py", "native room, X, mode and pose predicate"),
}

FIELDS = ("segment", "segment_name", "name", "body_offset", "body_method",
          "review_status", "prototype_owner", "review_scope",
          "known_direct_callers", "outgoing_named_calls")


def catalog_rows(recovery=None):
    if recovery is None:
        with CATALOG.open(newline="", encoding="utf-8") as source:
            rows = list(csv.DictReader(source))
        for row in rows:
            _set_review(row)
        return rows
    recovery = Path(recovery)
    with (recovery / "symbols.csv").open(newline="", encoding="utf-8-sig") as source:
        symbols = list(csv.DictReader(source))
    callers, outgoing = {}, {}
    with (recovery / "named_calls.csv").open(newline="", encoding="utf-8-sig") as source:
        for edge in csv.DictReader(source):
            target = (int(edge["to_segment"]), edge["to_offset"].lower())
            callers[target] = callers.get(target, 0) + 1
            origin = (int(edge["from_segment"]), edge["probable_source_function"])
            outgoing[origin] = outgoing.get(origin, 0) + 1
    rows = []
    for symbol in symbols:
        row = {key: symbol[key] for key in FIELDS[:5]}
        _set_review(row)
        segment = int(symbol["segment"])
        row.update(known_direct_callers=callers.get((segment, symbol["body_offset"].lower()), 0),
                   outgoing_named_calls=outgoing.get((segment, symbol["name"]), 0))
        rows.append(row)
    return rows


def _set_review(row):
    status, owner, scope = REVIEWS.get((int(row["segment"]), row["name"]), (
        "indexed-only", "", "No semantic review recorded in this prototype catalog"))
    row.update(review_status=status, prototype_owner=owner, review_scope=scope)


def catalog_text(rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def catalog_summary(rows):
    """Count recorded routine reviews, not atomic rules or implementation progress."""
    counts = Counter(row["review_status"] for row in rows)
    return {"routine_markers": len(rows),
            **{status: counts[status] for status in ("partial", "reference-only", "indexed-only")}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check the existing catalog without writing")
    parser.add_argument("--source", type=Path, help="Optional original recovery directory to re-index")
    parser.add_argument("--summary", action="store_true", help="Print review counts without writing")
    args = parser.parse_args()
    rows = catalog_rows(args.source)
    expected = catalog_text(rows)
    if args.check:
        if not CATALOG.exists() or CATALOG.read_text(encoding="utf-8") != expected:
            raise SystemExit("Catalog is stale; run python -m tools.recovery_catalog")
    elif not args.summary:
        CATALOG.write_text(expected, encoding="utf-8", newline="")
    print(f"{len(rows)} named routine markers indexed; this is not a recovered-rule completion count")
    if args.summary:
        for status, count in catalog_summary(rows).items():
            if status != "routine_markers":
                print(f"{status}: {count}")


if __name__ == "__main__":
    main()
