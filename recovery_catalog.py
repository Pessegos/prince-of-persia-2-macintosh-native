"""Index known original routines without treating disassembly as recovered logic."""

import argparse
import csv
import io
from pathlib import Path


PROJECT = Path(__file__).resolve().parent
CATALOG = PROJECT / "RECOVERY_CATALOG.csv"

# These reviews cover specific ordinary branches, never an entire routine.
REVIEWS = {
    (2, "ReadKeyboard"): ("partial", "mac_input.py", "ordinary keyboard priority"),
    (2, "ResetFrameVars"): ("partial", "scene_prototype.py", "five/six-tick cadence only"),
    (3, "ComputeHalfRect"): ("partial", "render_opening.py", "climb 135-144 rectangle table"),
    (3, "DrawKidMeter"): ("partial", "combat_art.py", "ordinary health icons; upgrade effects missing"),
    (3, "DrawOppMeter"): ("partial", "combat_art.py", "ordinary guard health icons"),
    (4, "EnGarde"): ("partial", "combat.py", "ordinary guard skill and ready-pose decisions"),
    (4, "OpponentClose"): ("partial", "combat.py", "ordinary close-range decisions"),
    (4, "DoOppTumbleSeq"): ("partial", "combat.py;terrain.py", "forced rooftops, generator life flag, death-bank/Rnd(3), overlap and facing/tile vetoes; ordinary rooftop NPCs"),
    (4, "GetOppDeadSeq"): ("partial", "combat.py", "ordinary rooftop slot-parity corpse 195/228; special actors missing"),
    (4, "AnimChar"): ("partial", "sequence_runtime.py", "supported opcodes; others fail explicitly"),
    (4, "GetCharCol"): ("partial", "terrain.py", "ordinary signed coordinate conversion"),
    (4, "GetRow"): ("partial", "terrain.py", "signed row conversion"),
    (4, "CheckBarr"): ("partial", "terrain.py", "standing-turn mode-7 exclusion; full barriers not translated"),
    (4, "CheckCollide1"): ("partial", "terrain.py", "unarmed grounded front-only versus armed front/rear within port sweep"),
    (4, "ClipChar"): ("reference-only", "render_opening.py", "full native clipping pipeline not translated"),
    (6, "Falling"): ("partial", "terrain.py", "ordinary rooftop falls and grabs"),
    (6, "HitFloor"): ("partial", "terrain.py", "ordinary speed thresholds and sequences"),
    (6, "GenCtrl"): ("partial", "scene_prototype.py;terrain.py", "tested locomotion/sword/ledge branches; ordinary release 11/23, DoJumpHang/99 missing"),
    (6, "StairClimbing"): ("partial", "scene_prototype.py", "ordinary ledge entry and standing crouch fallback via 1068 only"),
    (6, "DoStepFwd"): ("partial", "mac_input.py;terrain.py", "ordinary clearance/caution; dynamic tiles missing"),
    (6, "DoRunJump"): ("partial", "terrain.py", "ordinary two-cell takeoff alignment"),
    (6, "CheckOppGenPts"): ("partial", "opponent_generation.py;combat.py", "tested rooftop reinforcement branches"),
    (6, "CutChar"): ("partial", "terrain.py", "horizontal cuts and downward priority; vertical gaps remain"),
    (6, "CheckStab"): ("partial", "combat.py", "ordinary contact/damage, forced and generator-enabled tumbles"),
    (6, "IsOppGenPtWithTumbleOn"): ("partial", "opponent_generation.py;combat.py", "current room packed-life 0x80 flag"),
    (23, "DrawRoofBackWall"): ("partial", "render_opening.py", "ordinary background fill/SHAP table"),
    (23, "DrawRoofFloor"): ("partial", "render_opening.py", "floor masks/ledge exceptions; conditional passes incomplete"),
    (23, "DrawRoofLedgeInBack"): ("partial", "render_opening.py", "row-owned ledge mask subset"),
    (23, "DrawRoofGlass"): ("partial", "opening_animation.py;scene_prototype.py", "opening window/glass timeline"),
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check the existing catalog without writing")
    parser.add_argument("--source", type=Path, help="Optional original recovery directory to re-index")
    args = parser.parse_args()
    rows = catalog_rows(args.source)
    expected = catalog_text(rows)
    if args.check:
        if not CATALOG.exists() or CATALOG.read_text(encoding="utf-8") != expected:
            raise SystemExit("Catalog is stale; run python recovery_catalog.py")
    else:
        CATALOG.write_text(expected, encoding="utf-8", newline="")
    print(f"{len(rows)} named routine markers indexed; this is not a recovered-rule completion count")


if __name__ == "__main__":
    main()
