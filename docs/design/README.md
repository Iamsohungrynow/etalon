# Studio visual reference

`studio-reference.html` is the frontend reference supplied on 2026-10-15, stored unchanged. It is a visual mock with placeholder content, not a spec: `ui-ux-spec.md` remains the source of truth for Studio until it is updated.

What maps onto Studio: the three-column body (archive list | dark stage | inspector) matches the Setup screen (structure tree | viewport | inspector, `ui-ux-spec.md` §5.2). It also matches the Results field viewer, which is a black canvas with a key-value inspector beside it.

Conflicts to decide before a Studio session builds from it:

| Reference | `ui-ux-spec.md` / CLAUDE.md | Decision needed |
| --- | --- | --- |
| Light paper theme (`#F2F0E4`, black ink), `color-scheme: light` | §7: dark theme default (`#0E1013`), light as an option | Which theme is the default; whether §7 tokens are replaced |
| Seven-colour spectrum gradient as the selection/accent | §7: one accent colour (amber `#E8B34A`) | Whether the spectrum replaces amber |
| Inter + JetBrains Mono loaded from Google Fonts at runtime | §3.5, CLAUDE.md: no runtime font or asset fetches; fonts bundled | None: the same fonts must be bundled |
| Perpetual marquee tickers, particle animation | §7: 120 ms panel motion only, nothing perpetual | Whether any ticker survives, e.g. a static status strip |
| Random "live stream" and procedural figure | §3.3: numbers with units, from the solver | None: only real solver output ships |
| `cursor: crosshair` everywhere | — | Probably only over canvases |
| Placeholder researchers and institutions | — | None: placeholder people must not ship |
