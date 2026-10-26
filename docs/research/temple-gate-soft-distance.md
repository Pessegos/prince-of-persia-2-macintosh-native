# Temple general contact-distance selector

The original4:5eae selector now runs with real ReadCell, GetBarrCode,
GetBarrDistFromFace, AdjustRoom, GetFCharX/GetDist1 and floor/space predicates.
This replaces the isolated scalar-distance boundary in the earlier research,
but does not yet compose it inside the soft-contact caller or enable gameplay.
Actor/collision rectangles, cached frame dx/flags, bars flag and displayed/
neighbor rooms remain prepared inputs. No native endpoint is stubbed.

The selector reads the current supporting cell first. A nonnegative barrier
distance below51 wins and writes distance-kind1. A farther barrier uses the
safe sentinel42 and kind2. If no current barrier wins, it reads the forward
cell using the original opposite direction table to the contact search.
The most recent ReadCell cache/room bases are retained; they are not restored.

A forward gap, mobile floor or kind30 measures the supporting-foot edge and
writes kind0. Ordinary clear forward floor instead returns42/kind2. Kinds
6/22/2/34 have the one-pixel edge adjustment, with a distinct zero-edge
safe fallback. Types23/24 have directional/current-versus-forward offsets:
the selected slope paths compute a distance but **preserve** the incoming
distance-kind word. The canary71 in the report proves that preservation;
it is not a new valid kind value invented by the model.

Foot position uses cached frame dx minus the low six flag bits, relative to
facing. The original5:48b0 extends its argument to32 bits **before** SUBQ.W4
changes only its low word. Arguments0..3 therefore divide65532..65535,
not-4..-1. Near the negative signed limit, the subtraction likewise keeps
the sign extension rather than re-extending its new low word. Independent
native boundary calls verify this unusual rule. This is relevant to later
offscreen-actor coordinate auditing; it is not a general keyboard/AI fix.

## Evidence

`tools/probe_temple_gate_soft_distance.py` compares80,296 calls with zero
mismatches:65,880 over all declared room cells of levels10-13,14,400 tile/
foreground/body-height/bars/signed controls, and16 explicit word-subtraction
boundaries. Actual-room fixtures cross both facings, three cached frame
dx/flag pairs and three body positions. Synthetic controls cover18 forward
kinds, both slope types, short/tall bodies and signed extremes; they are
not extra original content or demonstrated reachable trajectories.

Whole A5 comparisons permit only predicted cache, room-base pointers,
anchor, distance-kind and remainder writes. Actor, saved actor, TROBs and
level bytes stay unchanged. Ordered cell requests and signed return values
are checked. DATA's barrier tables and the -2..11 column-anchor domain are
asserted before probing. Resource/frame loading, physical body generation,
overlap banks, animation, support and outer FrameAdv remain excluded.

Eleven asset-free regressions pin sentinel-versus-edge meaning,51 boundary,
current-cell priority, passable-gate anchor retention, frame-foot offsets,
one-pixel adjustment, slope preservation, crevice height, bar flag and mixed
word/long arithmetic. All459 temple reference tests pass.

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_gate_soft_distance --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_gate_soft_distance_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_gate_soft_distance_reference
```

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Compared-output SHA256:
`b3a96808c2565a6a42ca2698d9bb02e50fa186c82746d467a43d6f103cc636d6`.
Original bytes and detailed reports remain ignored locally.

Next compose the real selector after JumpSeq50 in4:60e4, preserving the
cached previous frame before any later AnimChar. Then construct the two
overlap banks in actual collision order. No full playable-temple, rendering,
audio, damage/death or repeated-world equivalence is claimed.
