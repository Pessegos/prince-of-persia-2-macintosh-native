# Temple Permanent-Pressure Setup

Research only, based on `fc6c8f1f`. Independently executes the complete
permanent-pressure wrapper5:252e-2552 and timer setter5:22b8-22ee. This
complements the [connected actor/plate trace](temple-actor-plate-lifetime.md),
which already executes the downstream PushPlate body on five rock-only sources.

## Exact Contract

The six-word cell cache is supplied. The wrapper masks the cached foreground
to its low byte, writes31 to that link's timer, then calls PushPlate with
explicit `(cached kind, link index)` arguments. The timer/cache are captured
at that call boundary, so ordering is checked rather than inferred from the
final bytes. D3 is saved/restored as a complete32-bit register.

The wrapper neither validates the tile kind nor reads the map to reconstruct
the cached cell. Synthetic kind controls therefore establish passthrough,
not gameplay admission. Actual admission remains CheckPress's responsibility.

No source-depressed-bit, press flag, actor, MOB or TROB effect belongs to
this bounded wrapper: all its observed level writes are confined to the
selected timer word. Such downstream effects are covered only where the
separate connected probe actually executes PushPlate and its links.

## Evidence And Limits

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_permanent_pressure --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_permanent_pressure_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_permanent_pressure_reference
```

**1,304 native/reference comparisons, zero mismatches**:

-544 original-marker cases: all68 header-admitted original plates, eight
  explicitly supplied old timer values each;
-544 matching supplied depressed-flag controls;
-216 supplied cache/kind controls, including link indices0/255, negative
  foreground words, kind34 (absent from original source markers), and kinds
  which ordinary CheckPress would not admit as plates.

The entire level, six-word cache, current/saved actors, both supplied bank
canaries/counts, press flag and D3 are checked. One supplied endpoint remains:
PushPlate5:240c records arguments/timer/cache and returns0; its body is NOT
executed here. No ReadCell, actor admission, link activation, timer release,
sound, pixels, save/reset or runtime temple integration is claimed.

Six asset-free tests pin ordering, byte-limited writes, signed foreground,
table endpoints, passthrough and validation boundaries. Executable SHA256 is
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`;
compared-output digest is
`5311754d2d1d6b78ad70d5ba95feb0a654b143482bd8fe0501bd3efd0af2f63e`.
The ignored report records all four LEVL hashes.

Follow-up evidence: [gate TROB animation](temple-gate-animation.md) and
[connected mixed gate/rock lifetimes](temple-mixed-lifetime.md). Actual
support/contact and rock motion in the mixed chain remain separate work.
