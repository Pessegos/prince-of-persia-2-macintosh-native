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
    (3, "CheckGateInFore"): ("partial", "pop2/caverns.py;pop2/scene_prototype.py", "ordinary moving-gate body masks by physical row, supporting column and mode; 80 native admission checks; full NPC-bank and special crush redraw paths partial"),
    (4, "IsLedge"): ("partial", "pop2/terrain.py", "ordinary empty/floor catch geometry and left-facing phase-zero gate veto (512 native gate checks); DoJumpUp gate override retained; special floor branches partial"),
    (2, "ReadKeyboard"): ("partial", "pop2/mac_input.py", "ordinary keyboard priority"),
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
    (5, "CheckPress"): ("partial", "pop2/loose_floors.py;pop2/pressure_plates.py", "supporting-foot and pose/mode/height admission for loose floors and pressure plates; special actor host incomplete"),
    (5, "ATMSpikes"): ("partial", "pop2/wall_spikes.py", "cavern visible-room/left-neighbor MOB lifetime, retract/hold phases and cues 282/284; 256 native phase updates; shared MOB bank incomplete"),
    (5, "DrawObjSpikes"): ("partial", "pop2/wall_spikes.py;pop2/caverns.py;pop2/level_rendering.py", "cavern back/front and blood banks, DATA offsets and masked transfer; all 18 representative native draw commands matched; other environments omitted"),
    (5, "MobSpikes"): ("partial", "pop2/wall_spikes.py;pop2/scene_prototype.py", "outward phase 1/2 hit admission; native Prince trigger/hit/sequence/alignment comparisons over 23400 supplied-bound cases; temple/special actors omitted"),
    (5, "TriggerSpikes"): ("partial", "pop2/wall_spikes.py;pop2/scene_prototype.py", "cavern idle activation and held-pose renewal, shared MOB capacity not unified with other hazards"),
    (4, "GetBarrCode"): ("partial", "pop2/terrain.py;pop2/scene_prototype.py", "wall-spike type 3 reserved for explicit DoStepFwd query; run startup and ordinary collision keep type 4; native close-start clearances 39/17 verified; other barrier special cases partial"),
    (5, "PushPlate"): ("partial", "pop2/pressure_plates.py", "link timer, depression after chain traversal, ordinary/permanent press and click cue; level-three reverse plates integrated"),
    (5, "Trigger"): ("partial", "pop2/pressure_plates.py", "native linked target traversal; level-three stone gates, exits and all nine projectile traps dispatched"),
    (5, "TriggerGate"): ("partial", "pop2/pressure_plates.py", "level-three reverse-plate dispatch; special level/story and closing-on-actor branches missing"),
    (5, "TriggerObject"): ("partial", "pop2/pressure_plates.py;pop2/darts.py;pop2/scene_prototype.py", "level-three closed exits and fresh-plate idle-shooter admission; other environment branches missing"),
    (5, "CloseExit"): ("partial", "pop2/cavern_state.py;tools/extract_caverns.py", "native first-room 79/47/0 closure retained separately from pressure-driven exit opening"),
    (5, "GetLinkNext"): ("partial", "pop2/pressure_plates.py", "signed next index from native ten-byte link records"),
    (5, "GetLinkTimer"): ("partial", "pop2/pressure_plates.py", "native initial timer with portable session override"),
    (5, "ChangeLinkTimer"): ("partial", "pop2/pressure_plates.py", "portable timer mutation; no Macintosh handle storage"),
    (5, "GetLinkCell"): ("partial", "pop2/pressure_plates.py", "native signed target cell and unassigned-link sentinel"),
    (5, "GetLinkRoom"): ("partial", "pop2/pressure_plates.py", "native one-based target room converted at the terrain boundary"),
    (8, "DrawCaveGateMovable"): ("partial", "pop2/caverns.py;tools/extract_pressure_plates.py", "native two-layer shapes, quarter-phase displacement and clips; 636 individual and 504 combined room/floor/climb command-list comparisons including plates"),
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
    (6, "TryPickUp"): ("partial", "pop2/potions.py;pop2/scene_prototype.py", "current/forward normal and mega flask selection; 644 native admission/alignment/sequence/removal cases; sword and special flask branches omitted"),
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
    (3, "DrawOppMeter"): ("partial", "pop2/combat_art.py", "ordinary guard health icons"),
    (4, "EnGarde"): ("partial", "pop2/combat.py", "ordinary range/pose decisions, selected retreat/turn history, far-run anticipation limits and pursuit; level-5 bridge/special actors missing"),
    (4, "OpponentClose"): ("partial", "pop2/combat.py", "ordinary close-range decisions"),
    (4, "WaitingEngarde"): ("partial", "pop2/combat.py", "ordinary multi-guard spacing and same-facing pursuit; self-nearest obstacle branch missing"),
    (4, "GenFight"): ("partial", "pop2/combat.py", "102-pixel spacing plus 36 per later nearby NPC, including corpses; full native bank lifecycle missing"),
    (4, "GetCellsInFront"): ("partial", "pop2/combat.py;pop2/terrain.py", "ordinary facing-relative front cells from controller anchor column"),
    (4, "GetDist1"): ("partial", "pop2/combat.py;pop2/terrain.py", "ordinary supporting-foot distance, including post-turn guard spacing"),
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
    (4, "GetCharCol"): ("partial", "pop2/terrain.py", "ordinary signed coordinate conversion"),
    (4, "GetRow"): ("partial", "pop2/terrain.py", "signed row conversion"),
    (4, "CheckBarr"): ("partial", "pop2/terrain.py", "standing-turn mode-7 exclusion; full barriers not translated"),
    (4, "CheckCollide1"): ("partial", "pop2/terrain.py", "unarmed grounded front-only versus armed front/rear within port sweep"),
    (4, "ClipChar"): ("partial", "pop2/caverns.py;pop2/scene_prototype.py", "cavern ordinary top clipping and Prince exit top/right rectangle; full native clipping pipeline not translated"),
    (4, "IsCharNonViewable"): ("partial", "pop2/render_opening.py", "settled Prince/ordinary guard rooftop corpses except native rooms 15/16/19; guard variant 228 included"),
    (6, "Falling"): ("partial", "pop2/terrain.py", "ordinary rooftop falls and grabs"),
    (6, "HitFloor"): ("partial", "pop2/terrain.py;pop2/lava.py;pop2/scene_prototype.py", "ordinary speed thresholds and sequences; Prince lava-tile landing precedes impact damage and preserves airborne mode (120 native dispatch checks)"),
    (6, "GenCtrl"): ("partial", "pop2/scene_prototype.py;pop2/terrain.py", "tested locomotion/sword/ledge and cavern Up exit admission/alignment to SEQS:70; ordinary release 11/23/99 with DoJumpHang preview; hard-fall mode-5 reset (72 native checks); gate climb clearance/SEQS:73 (6144 native checks); full input latches/special levels partial"),
    (6, "StairClimbing"): ("partial", "pop2/scene_prototype.py", "ordinary ledge entry and standing crouch fallback via 1068 only"),
    (6, "DoStepFwd"): ("partial", "pop2/mac_input.py;pop2/terrain.py", "ordinary clearance/caution; dynamic tiles missing"),
    (6, "DoRunJump"): ("partial", "pop2/terrain.py", "ordinary two-cell takeoff alignment"),
    (6, "CheckOppGenPts"): ("partial", "pop2/opponent_generation.py;pop2/combat.py", "tested rooftop reinforcement branches"),
    (6, "IsTimeToGenOpp"): ("partial", "pop2/opponent_generation.py", "ordinary rooftop eligibility and DIVU/SWAP full-word counter gate; full native NPC bank lifecycle missing"),
    (6, "CutAllOpponents"): ("partial", "pop2/combat.py", "horizontal Prince cuts carry ordinary running/jump poses and movement flags; stationary, vertical and special-actor branches missing"),
    (6, "TransferOppInfo"): ("partial", "pop2/combat.py", "ordinary horizontal runner carry, 510-pixel coordinate rebase and persistent actor identity; full native record fields missing"),
    (6, "CutChar"): ("partial", "pop2/terrain.py", "horizontal cuts, downward priority and native room-15 right-cut veto; vertical gaps remain"),
    (6, "CheckStab"): ("partial", "pop2/combat.py;pop2/terrain.py", "ordinary contact/damage, type-2 guard death method 14, player/NPC flat alignment, forced and generator-enabled tumbles"),
    (6, "TestStrike"): ("partial", "pop2/combat.py;pop2/scene_prototype.py", "ordinary sword contact, row/strict 15-pixel height gate, no blanket grab/climb immunity; special attacks missing"),
    (6, "GetCharStrikeRanges"): ("partial", "pop2/combat.py", "ordinary Prince/type-2 NPC ranges, facing, sword and engagement flags; special actors missing"),
    (6, "GetOppIdxClosestToKid"): ("partial", "pop2/combat.py", "ordinary living same-floor nearest actors on each side; full native vertical/type candidate filtering missing"),
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
