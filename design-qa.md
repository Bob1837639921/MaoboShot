# Design QA

## Scope

- Visual target: the selected light ManboShot translation bubble, revised with the user's tabby cat mascot.
- Implementation: transparent desktop pet window, compact result bubble, pet settings page, and existing full translation window handoff.
- Captures: 390 x 385 pet success state and 820 x 620 settings window.

## Comparison

- The implementation preserves the selected target's light surface, blue outline language, source/result hierarchy, AI status, close control, copy, read-aloud, and full-result action.
- The production bubble is intentionally reduced from the concept so it does not dominate the desktop; dual-engine details remain in the existing main translation window.
- The selected humanoid mascot was replaced by the approved tabby cat identity: forehead M marking, cheek stripes, brown-gray coat, ringed tail, raised paw, and blue scarf.
- The generated concept's pale grid background is removed at runtime without deleting the cat's eyes, muzzle, coat pattern, or scarf.

## Interaction QA

- P0/P1/P2 issues: none.
- Loading, streaming, success, partial failure, failure, and speaking states resolve through a tested state mapper.
- The bubble updates in place during streaming and auto-hides after completion.
- Copy, read-aloud, open-full-result, close, double-click, drag, context menu, tray visibility, and settings controls are wired.
- Pet size is adjustable from 70% to 140%; the saved scale updates sprite bounds and screen clamping.
- Manual lick-paw, blink, and jump actions are available from the context menu, while translation success triggers the jump automatically.
- The lick-paw action uses 8 transparent `192×208` frames with shared registration. The canonical idle artwork renders at frames 0 and 7 so action entry and exit do not resize or shift.
- Frame extraction, clipping checks, chroma despill, the generated contact sheet, and the application-level contact sheet passed visual review at production pet size.
- Pet position uses global logical coordinates, accepts negative-coordinate displays, clamps to the nearest available screen, and flips bubble alignment near left or right edges.
- Settings expose a native checkbox for visibility, pet-pack selection, and result-bubble visibility.
- Pet packs validate schema and reject sprite paths outside their own directory.

## Follow-up

- P3: Additional generated rows can add walking and greeting later through the same animation contract without changing the pet window or event wiring.

final result: passed
