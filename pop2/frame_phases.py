"""The world phases each gameplay tick runs after the Prince's controls.

See docs/research/frame-phase-order.md for the original FrameAdv order these
lists are compared against. The lists reproduce the port's existing order;
changing an entry changes gameplay timing and needs original evidence.

'entry' is the cut of a room crossing (CutAllOpponents 6:4382, PrepCut
2:532c): the phases before it on a crossing frame still see the room left
(ScenePrototype.room_left_view), as FrameAdv 2:626c-6290 does.
"""

# Each mode is one early-return branch of ScenePrototype.advance_animation.
WORLD_PHASES = {
    # A potion pick-up step (DoPickupEffect follows the SEQS step).
    'potion': ('terrain', 'combat', 'environment', 'entry', 'level_events', 'rebirth', 'audio',
               'render'),
    # Falling, sinking or dead: no controls, the SEQS keeps running.
    'falling': ('terrain', 'combat', 'environment', 'harbor', 'entry', 'level_events', 'rebirth',
                'audio', 'render'),
    # Hurt/blocked sword poses that refuse new controls.
    'locked': ('terrain', 'combat', 'environment', 'harbor', 'entry', 'level_events', 'rebirth',
               'audio', 'render'),
    # Level one's window escape drives the Prince itself.
    'opening': ('combat', 'audio', 'render'),
    'ordinary': ('terrain', 'combat', 'environment', 'harbor', 'entry', 'level_events', 'rebirth',
                 'audio', 'render'),
}
