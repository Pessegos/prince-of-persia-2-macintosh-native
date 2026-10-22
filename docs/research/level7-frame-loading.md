# Ruins Special-Actor Frame Loading

Independent headless research; no renderer/runtime changes. Related notes:
[preparation](level7-preparation.md) and
[initialization](level7-head-initialization.md).

```powershell
python -m tools.probe_level7_frames --source PATH_TO_RECOVERY --output rendered/level7-native-frames.json
python -m unittest -q tests.test_level7_frame_reference
```

## Original Loader

LoadFrame 4:2a8e selects from the installed opponent FRAM/AFRM handles.
The recursive listing omits the actor switch body at 4:2abc-2b91. The
probe executes those actual bytes, not the port's frame decoder or a
replacement dispatch table. It compares the complete 10-byte frame and
8-byte attachment copied into the original A5 scratch buffers.

The original Head.rsrc has FRAM 750 with 141 records and AFRM 750 with
one record. For directly supplied poses 149-289 inclusive:

| Working Type | FRAM Record Index |
| --- | --- |
| 7, head | pose - 149 |
| 8, head variant | pose - 149 + 43 when pose <=181; otherwise pose - 149 |
| 11, serpent | pose - 149 |

There were zero differences in 423 native/reference comparisons (141 per
type), with no stubbed services. Actual resource handles are installed by
the harness, and the original routine executes to return. All 127 distinct
nonnegative shape references in FRAM exist in the original SHAP bank when
resolved through SHPL 750. No original data files are distributed.

Do not apply the ordinary guard's special pose remapping to this family,
and do not treat the type-8 variant as a palette-only difference. The +43
offset is conditional; applying it to every pose would select the wrong
record after pose 181.

## Scope

The resource parser is the existing Macintosh resource-fork parser. The
comparison of frame selection/copying is original native code against
direct byte slicing; it does not call parse_frame_records or GuardArtwork.

The tested pose domain is supplied, not a claim that every pose is reachable
for every type. Other poses/types are deliberately rejected by the research
reference. The three synthetic unit tests check its bounds/remap threshold;
they do not perform native comparisons without the separate probe command.

This does not establish SHAP rasterization, palettes, mirrored placement,
neck alignment, controller/animation scheduling or full visual parity.
Frame loading can now be reused natively in the controller-routing probe,
but shape bounds and controller effects need their own explicit boundaries.
