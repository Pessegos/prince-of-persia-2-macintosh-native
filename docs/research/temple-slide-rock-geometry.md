# Temple Sliding-Rock Geometry

Research/reference evidence only. This block validates the real cell reader,
span scan and two-row stopping predicate independently of motion. No production
port files/assets are changed, and no native endpoint is supplied.

## Native Path

| Routine | CODE Resource Offsets | Tested Role |
| --- | --- | --- |
| Two-band predicate | 10:1656-1680 | Scan row-1, then row0 only if first passed |
| Span predicate | 10:1ca4-1d40 | Inclusive column scan with anchor/distance cap |
| IsSpace | 3:4eb2-4ee4 | Exact kind classification, not IsWall |
| ReadCell | 4:27ee-28a8 | Normalized cached cell, kind and foreground |
| Neighbor normalization | 4:26e2-27e0 | Horizontal/vertical room traversal |
| Undefined cell | 4:28b6-29c0 | Temple fallback, including level13 view exceptions |
| FirstInRow | 4:322a-3262 | Normal rows and negative-row sentinel convention |
| CalcBlue | 5:0004-0066 | Real per-room tile/foreground bases |
| Signed division | 19:4bb0/4bd0/4bfe | Native truncation toward zero |

Offsets include the four-byte CODE header. Original source resources remain
read-only. Inputs are supplied records, selected view rooms, original levels
and explicitly identified in-memory counterfactual copies, not live gameplay.

## Predicate Meaning

For record X, stored row and originalX:

1. First column is `trunc((signedX+2)/51)`.
2. Distance is `signedWord(min(signedLength, unsignedWord(originalX)-signedX))`.
3. Last column is `trunc((signedX+distance)/51)`.
4. Read columns first..last inclusive in the record's room and stored row plus
   the supplied row offset. Stop immediately on a rejected tile.
5. Reject IsSpace kinds **0,9,27,47,49**, and separately marker**25**. All other
   tested raw words pass, including walls. This is not an empty-space test.
6. If first>last, return true without reading any cell. Nonpositive length
   does not itself guarantee no reads: truncation can put both ends in one cell.

The higher predicate10:1656 calls the scan with offset-1/length51. Only when
that passes does it call offset0/length51. It returns the conjunction. The
length82/offset-1 variant is separately tested because presentation10:1456
also uses that scan shape; this does not validate presentation itself.

The X+2 start, originalX cap and unsigned originalX conversion all matter.
Do not replace the scan with an actor-width rectangle, floating-point floor,
an IsWall test or a generic "there is room to move" query. The name `filled`
now replaces provisional `clear` in the earlier supplied-endpoint motion probe.
It denotes this classification and vacuous truth, not pixel solidity or a
complete character-collision predicate.

## Cell Traversal And Cache

The reference decodes raw room arrays independently of the port LevelMap.
Native link order is left/right/above/below, each a word in an eight-byte entry
at level+2080. Coordinates normalize by10 columns/3 rows across links.

Horizontal traversal is attempted first. If its link is missing, the native
normalizer still attempts vertical traversal from the original room; a corner
request can find a valid vertical-then-horizontal path. If the horizontal link
exists, traversal through that room takes precedence. Explicit synthetic
topologies and the actual four level maps both exercise these rules.

The cache stores **normalized**, not necessarily requested, room/column/row.
Repeated normal-cell reads can use the native coordinate-cache fast path;
repeated out-of-range requests may normalize again. Tile/foreground still read
from level data. Compared cache words in memory order are:
`kind, foreground, cellIndex, room, column, row` at A5-34b0..-34a6.

Normal first-in-row values are10*row. The native negative-row path instead
uses10*(row+1)-1 in the tested sentinel range. For example, an explicit room0,
column-1,row-1 query normalizes column to9 but retains row-1, giving index8.
This is a cache/sentinel fact, not a live room cell to render or collide with.

For a missing or above-header-maximum room, temple undefined tiles are20 and
foreground0, except level13 when A5-4fc2 (the supplied view room) is4 or13:
then undefined kind is0. The view room is not necessarily the queried room.
Do not generalize these temple fallbacks to other environments.

## Native Evidence

```powershell
python -m tools.probe_temple_slide_rock_geometry --source PATH_TO_RECOVERY --output rendered/temple-slide-rock-geometry.json
python -m unittest -q tests.test_temple_slide_rock_geometry_reference
```

32,082 native/reference comparisons pass, with **no supplied native services**:

| Cases | Count |
| --- | --- |
|Cold and repeated cell reads: all32 rooms,columns-1..10,rows-1..3,view variants|23040|
|Explicit room0 cold/repeat controls with the same coordinate/view range|720|
|Two-band predicate at all960 ordinary cell positions in each of four levels|3840|
|Scans around all12 original tile25 anchors, three offset/length variants|1935|
|Five controlled room-link topologies, including diagonal precedence/fallback|175|
|Resolved room above the supplied header maximum|1|
|X/anchor/length arithmetic boundaries, signed and unsigned cases|2268|
|Raw kinds0..63 plus words8000/ffff/7fff in filled bands|67|
|Every rejection kind at each scanned position/row plus outside-band controls|36|

The raw-kind controls reject exactly the six listed words. The short-circuit
controls return false for24 in-band placements and true for12 outside-band
placements. On the actual maps, the both-band predicate passes1671 positions
and rejects2169. These are supplied coordinate samples, not reachable states.

Each comparison checks the return word, complete ordered ReadCell requests,
all six cache words, whole level, both62-byte actor buffers, unchanged16-byte
mob and unrelated512-byte bank guards. The comparison does not merely count
passing booleans: traversal order and final cached state must also agree.
18 synthetic unit tests require no original assets or Unicorn installation.

Original executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Output SHA256:
`a1c1097d10f607770b55401e2454e498d73aafffe808bf0fdeacdac282c2e432`.
The ignored report records all four original level hashes and outcome counts.

## Remaining Work

This probe proves the predicate bodies and bounded raw cell traversal, not
complete motion/world composition. The subsequent
[connected-update probe](temple-slide-rock-update.md) now combines them with
motion10:1d5c, the following crush-admission10:16f6 call, real bank updates/
compaction and activation traces, preserving real cache effects. The actual
actor reactions10:1b04/5:3cee/6:1a84, rendering,
TriggerObject admission, FrameAdv scheduling, collision consequences and save/
restart persistence remain separate work. No complete temple/campaign claim.
