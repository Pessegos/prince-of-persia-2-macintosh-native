# Ruins Head Neck Alignment

This recovers the coordinate helper, not the event that attaches a head or
the damage/escape rules while attached. No runtime changes are included.

```powershell
python -m tools.probe_level7_neck_alignment --source PATH_TO_RECOVERY --output rendered/level7-native-neck-alignment.json
python -m unittest -q tests.test_level7_neck_reference
```

## Original Inputs

AlignHeadOnKidNeck 7:0006 calls GetObj 3:3e7c with object kind 2 and slot
0. The native object lookup runs against a supplied 28-byte-record object
list; a nonmatching slot precedes the Prince in the fixtures. The matching
object supplies drawing X/Y at +0/+2 and an index at +6.

Head.rsrc's type-zero resource 755 is 1,408 bytes: 352 signed word pairs.
The helper indexes it by that drawn-object +6 value, with stride 4. It is
an alignment table, not an ordinary enemy pose/HP record. The first word
is added to drawing Y; the second supplies the horizontal adjustment.
Mapping a live Prince pose into the drawn-object index is a separate
renderer/producer question, not certified by supplying table indices.

## Coordinate Rule

Let `(dy, dx)` be the selected word pair and `(px, py)` the Prince's drawn
object coordinates. Work with native facing values -1/0:

1. If head and Prince face the same direction, replace dx with
   `-dx - head_sprite_width - K`, where K=17 for type 7 and K=25 for type 8.
2. For type 8, add 10 to dx (both same-facing and opposite-facing cases).
3. If head facing is 0, negate dx.
4. Drawing X/Y become `(px + dx, py + dy)` in A5-0x34c4/-0x34c2.
   Working native X becomes drawing X +207 in A5-0x5052.

This helper does not directly assign working Y at A5-0x5050. Do not replace
it with a generic actor-anchor offset or confuse drawing coordinates with
the native X origin. If GetObj finds no Prince object, all three tested
coordinate outputs remain unchanged and no metadata/image-size service runs.

## Native Comparison

The full original alignment helper and original GetObj execute. All 352
metadata entries are exercised with both head types, both head and Prince
facings, two real head sprite sizes and two supplied Prince drawing points:
11,264 comparisons, zero differences. Eight missing-object controls also
pass. Whole LEVL bytes remain unchanged.

The only supplied services are movable-handle lock/unlock (inert, fixed
harness storage) and GetImgSize 17:673a. The latter returns the dimensions
from actual Head SHAP headers for sprite indices 0/33, not invented widths.
It is requested only when the facings match, in 5,632 cases. Neither the
Macintosh memory manager nor original SHPL image-size lookup is certified.

Seven synthetic tests verify the independent formula and its type/facing
bounds without needing resources. Original resource parsing and SHAP header
dimensions are shared inputs, not separate proof of their binary formats.

## Remaining Integration Work

Supply the actual rendered Prince object, choose the current head sprite
through the verified frame loader, and call alignment at the original
attachment/draw points. Event reachability, shape pixels/palettes, ordering,
occlusion, neck damage, shake-off, head mode transitions and scheduling remain
separate work. There is no visual or full-game AI parity claim here.
