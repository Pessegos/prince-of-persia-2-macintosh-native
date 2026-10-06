"""Index known original routines without treating disassembly as recovered logic."""

import argparse
import csv
import io
from pathlib import Path

from pop2.paths import PROJECT_DIR


CATALOG = PROJECT_DIR / "docs" / "RECOVERY_CATALOG.csv"

# These reviews cover specific ordinary branches, never an entire routine.
REVIEWS = {
    (2, "ReadKeyboard"): ("partial", "pop2/mac_input.py", "ordinary keyboard priority"),
    (2, "ResetFrameVars"): ("partial", "pop2/scene_prototype.py", "five/six-tick cadence only"),
    (3, "ComputeHalfRect"): ("partial", "pop2/render_opening.py", "climb 135-144 rectangle table"),
    (3, "DrawKidMeter"): ("partial", "pop2/combat_art.py", "ordinary health icons; upgrade effects missing"),
    (3, "DrawOppMeter"): ("partial", "pop2/combat_art.py", "ordinary guard health icons"),
    (4, "EnGarde"): ("partial", "pop2/combat.py", "ordinary guard skill and ready-pose decisions"),
    (4, "OpponentClose"): ("partial", "pop2/combat.py", "ordinary close-range decisions"),
    (4, "DoOppTumbleSeq"): ("partial", "pop2/combat.py;pop2/terrain.py", "forced rooftops, generator life flag, death-bank/Rnd(3), overlap and facing/tile vetoes; ordinary rooftop NPCs"),
    (4, "GetOppDeadSeq"): ("partial", "pop2/combat.py", "ordinary rooftop slot-parity corpse 195/228; special actors missing"),
    (4, "AnimChar"): ("partial", "pop2/sequence_runtime.py", "supported opcodes; others fail explicitly"),
    (4, "GetCharCol"): ("partial", "pop2/terrain.py", "ordinary signed coordinate conversion"),
    (4, "GetRow"): ("partial", "pop2/terrain.py", "signed row conversion"),
    (4, "CheckBarr"): ("partial", "pop2/terrain.py", "standing-turn mode-7 exclusion; full barriers not translated"),
    (4, "CheckCollide1"): ("partial", "pop2/terrain.py", "unarmed grounded front-only versus armed front/rear within port sweep"),
    (4, "ClipChar"): ("reference-only", "pop2/render_opening.py", "full native clipping pipeline not translated"),
    (6, "Falling"): ("partial", "pop2/terrain.py", "ordinary rooftop falls and grabs"),
    (6, "HitFloor"): ("partial", "pop2/terrain.py", "ordinary speed thresholds and sequences"),
    (6, "GenCtrl"): ("partial", "pop2/scene_prototype.py;pop2/terrain.py", "tested locomotion/sword/ledge branches; ordinary release 11/23, DoJumpHang/99 missing"),
    (6, "StairClimbing"): ("partial", "pop2/scene_prototype.py", "ordinary ledge entry and standing crouch fallback via 1068 only"),
    (6, "DoStepFwd"): ("partial", "pop2/mac_input.py;pop2/terrain.py", "ordinary clearance/caution; dynamic tiles missing"),
    (6, "DoRunJump"): ("partial", "pop2/terrain.py", "ordinary two-cell takeoff alignment"),
    (6, "CheckOppGenPts"): ("partial", "pop2/opponent_generation.py;pop2/combat.py", "tested rooftop reinforcement branches"),
    (6, "CutChar"): ("partial", "pop2/terrain.py", "horizontal cuts and downward priority; vertical gaps remain"),
    (6, "CheckStab"): ("partial", "pop2/combat.py", "ordinary contact/damage, forced and generator-enabled tumbles"),
    (6, "IsOppGenPtWithTumbleOn"): ("partial", "pop2/opponent_generation.py;pop2/combat.py", "current room packed-life 0x80 flag"),
    (23, "DrawRoofBackWall"): ("partial", "pop2/render_opening.py", "ordinary background fill/SHAP table"),
    (23, "DrawRoofFloor"): ("partial", "pop2/render_opening.py", "floor masks/ledge exceptions; conditional passes incomplete"),
    (23, "DrawRoofLedgeInBack"): ("partial", "pop2/render_opening.py", "row-owned ledge mask subset"),
    (23, "DrawRoofGlass"): ("partial", "pop2/opening_animation.py;pop2/scene_prototype.py", "opening window/glass timeline"),
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
            raise SystemExit("Catalog is stale; run python -m tools.recovery_catalog")
    else:
        CATALOG.write_text(expected, encoding="utf-8", newline="")
    print(f"{len(rows)} named routine markers indexed; this is not a recovered-rule completion count")


if __name__ == "__main__":
    main()
