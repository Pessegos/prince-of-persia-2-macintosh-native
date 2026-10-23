# Temple Sliding-Rock Presentation

Research only, on `codex/temple-preparation`. This block recovers draw-queue
construction, not raster output or temple playability. Original resource offsets
include the CODE resource's four-byte header.

## Native Bodies

| Body | Original Address | Executed Scope |
| --- | --- | --- |
| ATMSlideRock | 10:1456-1644 | Full body, including temporary dimensions and restoration |
| Repeated decoration strip | 10:13ca-1454 | Full loop, including post-append phase write |
| Band scan | 10:1ca4 | Native scan and ReadCell/cache from the geometry probe |
| ATMLoose | 5:307c-3126 | Actual bank load, type6 dispatch and record writeback |
| GetRow | 4:3afa | Native row selection; IndexCell/FirstInRow also execute |
| ComputeMobRect | 5:32f6-33e6 | Full rectangle/projection body, supplied OffsetRect trap |
| MarkMobRedraw | 5:33fa-3456 | Full body up to the supplied redraw-list sink |
| AddMobObj | 5:346a-3566 | Full native queue append, not a replacement endpoint |

The DATA arrays at A5-4518 and A5-44fc contain fourteen signed heights and
widths. In particular A5-450c/A5-450a are heights for types6/7, **not shape
IDs**. Queue construction does not load SHAP resources or require a prepared
image cache. Later rasterization/resource selection is a separate gap.

## Admission And Temporary Geometry

Mob words remain `(X,Y,room,mark,control,type,row,originalX)`.

- Exact mark-1 returns before visibility, geometry or queue work. Mark1 does not.
- Otherwise native GetRow computes `t=word(Y-5)`, then
  `row=trunc(t/120)-(t<=0)`. Column is truncating signed X/51. IndexCell returns30
  outside row0..2/column0..9. Visibility receives this room/cell pair.
- Invisible returns without a band scan or dimension changes. Visibility is an
  explicitly supplied response, not independently recovered here.
- Visible saves **only height7**, then scans the upper band with length82.
  As established in [geometry](temple-slide-rock-geometry.md), true means no
  IsSpace/marker25 in the visited interval, not an empty band.
- A gap temporarily uses X+8, Y-112, height6=19 and
  width6=`word(min(width6, signed originalX - signed X))`. Native MarkMobRedraw(2)
  computes/intersects its rectangle before X/Y/width6 are restored. Height6
  becomes the saved height7.
- A filled band instead uses height6=109 and height7=111 during the body draws.

The main object is type7 at original X/Y. An extra type6 object at X+51,Y-2
is admitted by a strict comparison of signed temporary X with **unsigned**
originalX. Its screen cell uses the computed row without the IndexCell clamp.

Three decoration strips start at offsets `(79,-68)`, `(76,-37)`, `(66,-57)`
from original X/Y, with types8,8,9. Their outer admission has the same mixed
signed/unsigned comparison. The inner loop instead compares signed X with
signed originalX. Each tile advances X by36; phase `(initial strip X & 7)>>1`
is calculated once and written to the last queue record's word+24 after each
append. It is NOT recalculated after each step. Decoration screen cells use
the **stored** rock row, plus one column only for type8.

Finally X/Y/type are restored, and **both heights6/7 become the saved initial
height7**. All eight rock words and the physical bank are unchanged. Width6 is
restored. Unequal supplied initial heights6/7 are intentionally canonicalized,
not byte-for-byte restored. The computed screen cell and ReadCell cache are
transient outputs and are not restored. Control0/100 does not suppress drawing.

## Rectangles And Queue Writes

ComputeMobRect starts with signed-word
`(Y-height[type], X, Y+1, X+width[type])`. Current-room rectangles stay local.
Both native horizontal branches pass **-510**, including the left relation
(5:3380 loads `fe02`); do not silently replace that branch with +510. The
vertical branches pass -365 for below and +365 for above. These are 365,
not the trap-door probe's local 364 projection. Unrelated rooms copy an empty
rectangle. The relation tables here are supplied controls, not full room cuts.

AddMobObj appends even when the clip intersection is empty. Each record is
28 bytes; all written words and untouched padding are compared:

| Byte Offset | Value |
| --- | --- |
| 0,2 | X, supplied Y argument |
| 4,6,8 | 4, originalX, 0 |
| 10 | Unwritten: existing bytes preserved |
| 12 | type OR 0x80 |
| 14..20 | Intersected top/left/bottom/right |
| 22,24,26 | 0,0,-1; strip caller replaces word24 with phase |

The count at A5-4826 is incremented. **No native capacity check exists in
this append body.** The probe supplies128 slots, checks its own append budget
and compares prefix/tail canaries. This is bounded write validation, NOT native
overflow safety or a proposed production capacity.

## Evidence And Limits

```powershell
python -m tools.probe_temple_slide_rock_presentation --source PATH_TO_RECOVERY --output rendered/temple-slide-rock-presentation.json
python -m unittest -q tests.test_temple_slide_rock_presentation_reference
```

1,416 native/reference comparisons pass:

| Corpus | Comparisons |
| --- | --- |
| All12 actual anchors: selected X positions, marks-1/0/1, visibility and direct/bank entry | 804 |
| Supplied current/neighbor/unrelated view and visibility controls | 228 |
| Gap/filled bands, all eight initial phase values, deletion/direct/bank controls | 192 |
| Unequal heights, widths, Y/row boundaries, signed-anchor and clip controls | 192 |

3,292 native object appends are compared; this is an event count, not another
3,292 comparisons. All four declared branch checkpoints execute: gap303,
filled393, extra-type6 body423, decoration-tile loop2173.

Checks cover the complete16-byte rock, raw object storage/count/padding/guards,
fourteen heights and widths, ordered events, ReadCell requests/cache, unchanged
entire LEVL, both62-byte actors and the512-byte guarded physical bank/count.
Fifteen synthetic tests require no original resources, Unicorn or image assets.

The only supplied services are:

- Visibility5:3960: supplied boolean, queried room/cell recorded.
- Redraw-list sink5:19f8: records callback/rectangle/flag; no redraw list mutation.
- SectRect callback via A5-1f58: rectangle intersection and Pascal cleanup.
- OffsetRect trap5:33d0: signed translation and Pascal cleanup, opcode checked.

The queue append and all its later decoration metadata writes are native.
Actual pixels, real visibility admission, redraw scheduling, SHAP selection,
FrameAdv cadence, combined motion/contact/presentation traces and file-save/
restart remain open. The earlier [connected update](temple-slide-rock-update.md)
and [contact](temple-slide-rock-contact.md) probes do not retroactively gain
presentation coverage from this independent block.

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Output SHA256:
`b9ced3b2b48eb901981120b9254d9c18bdb76e17a2d92af19555e794f66b53df`.
The ignored report records original LEVL hashes and DATA dimensions/offsets.
