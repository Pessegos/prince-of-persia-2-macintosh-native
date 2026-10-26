# Ruins falling slabs, special actors and the viewport edge

The supplied level6 room4 Macintosh recording kills the first head with a
falling shelf. The port's contact predicate already knew the head's height,
but the environment only traversed the Prince and ordinary guards. Ruins
actors also have no TerrainMotion: their controller owns room/row and motion.
Both omissions prevented them from reaching the contact/crush path.

## Contact and crush

The frame-start debris pass now includes the actual room's ruins actors and
reads their Head FRAM records, using their physical Fighter room/row without
assigning ordinary terrain physics to them. The native rules are:

- Contact5:3642-376c requires native ALIVE<0, matching room and physical row,
  debris bottom strictly below the head threshold, and matching supporting
  column. Thresholds are actor Y-38 for types7/8, Y for serpents, Y-57 otherwise.
- Serpents also admit neighboring body cells: behind when supporting-foot
  distance>12, ahead when distance<6 (5:36e0-3762 and original direction DATA).
- Crushed6:28f0 excludes running poses5..14, pose109, non-ground modes except7,
  and actor type1. SetCharFloor6:2934/4:31fa then one point for the Prince or100
  for an NPC. The fatal special paths select146 for heads,169 for serpents;
  ordinary deaths select22 and nonfatal reactions52. A sword-hit head death154
  and serpent death174 are different paths and are not reused here.

The port applies HP through its existing direct-damage interface. Special
actors retain their own movement/animation/death-counter host, and a killed
banked head is released so another living head can be selected. No sword-hit
kill song, facing change or tension event is invented for a slab hit.

`tools/probe_ruins_slab_contact.py` executes14,256 original contact calls,
180 fatal special-actor crush/eligibility cases and50 IndexCell1 cases, with
zero mismatches. There are243 positive contacts and54 admitted crush cases;
the probe rejects an all-positive or all-negative fixture. Level-six fixture
LEVL2005 has its level header checked; original Head FRAM750 supplies offsets
and flags, and the report fingerprints the executable, level and frame bytes.
Passed actor and level bytes are guarded against contact writes.

Supplied endpoints: serpent-only LoadActor4:4ac0 reloads the prepared actor
and FRAM offset/flags; JumpSeq6:0006 records selection without decoding a native
sequence. Read-only original code executes the contact predicate, GetDist1,
SetCharFloor and DecLifePts. The crush comparison verifies the pending fatal
wound, not later HP/ALIVE registration. Full FrameAdv, generator-bank loading,
nonfatal recovery, audio and complete AI equivalence are excluded.

The scene regression drops the actual room4 type15 shelf onto its first head,
holding only horizontal AI control constant to isolate this collision. Real
gravity, contact, HP and animation run. It verifies146, then leaves/re-enters
without the developer teleport's optional enemy reset and verifies that the
head stays dead. A serpent scene verifies169; pure boundary cases cover both
facings of its adjacent body cells. These are not input-for-input video replays.

## The remaining mega-fall frame

The prior fixed-floor redraw handles the upper ledge and the cushioning-contact
frame. In the next frame, the loose floor has detached into a moving MOB3 slab.
The Prince's physical row is3 and his drawn bottom extends beyond the viewport.
The port's scenery pass painted all moving debris before every actor, so the
still-visible trousers covered that last slab even after fixed-floor redraw.

IndexCell1 at4:2a38 maps offscreen cells to bucket30, handled first by the
existing actor ordering. The compositor now restores visible debris within
the affected ordinary offscreen actor rectangle, including the existing native
floor-buffer repaint over that debris. Visible actors keep their normal
composition. This is a bounded correction to the scenery-first approximation,
not a claim to implement the complete native object comparator or rasterizer.

The actual Down-input room5->6->18 regression checks the upper descent,
cushioning-contact and following detached-slab frame separately, then verifies
the ordinary one-life-loss landing. Local before/after PNGs and the native
report remain ignored in `rendered/head-slab/`; no resource export is changed.
