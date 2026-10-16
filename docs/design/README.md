# Studio visual reference

`studio-reference.html` is the frontend reference supplied on 2026-10-15, stored unchanged. It is a visual mock with placeholder content, not a spec: `ui-ux-spec.md` remains the source of truth for Studio.

What maps onto Studio: the three-column body (archive list | dark stage | inspector) matches the Setup screen (structure tree | viewport | inspector, `ui-ux-spec.md` §5.2). It also matches the Results field viewer, which is a black canvas with a key-value inspector beside it.

## Decisions (2026-10-16, `docs/plan-u0.md` §2)

| Reference | `ui-ux-spec.md` / CLAUDE.md | Decided |
| --- | --- | --- |
| Light paper theme (`#F2F0E4`, black ink), `color-scheme: light` | §7: dark theme default (`#0E1013`), light as an option | Dark stays the default. The paper palette becomes Studio's light theme (§7 tokens updated). |
| Seven-colour spectrum gradient as the selection/accent | §7: one accent colour (amber `#E8B34A`) | Amber stays the one accent. The spectrum appears once, as a static 2 px stripe under the header, never behind text or data. |
| Inter + JetBrains Mono loaded from Google Fonts at runtime | §3.5, CLAUDE.md: no runtime font or asset fetches; fonts bundled | The same fonts, bundled (OFL-1.1, licence texts shipped). |
| Perpetual marquee tickers, particle animation | §7: 120 ms panel motion only, nothing perpetual | Dropped. A static bottom status strip shows real values instead. |
| Random "live stream" and procedural figure | §3.3: numbers with units, from the solver | Not shipped: only real solver output. |
| `cursor: crosshair` everywhere | — | Crosshair only over canvases and the viewport. |
| Square corners, hard 1 px rules, uppercase mono micro-labels, 900-weight 42 px headings | §7: 4/6 px radii, soft borders, 15/18/22 px headings | Square corners, crisper rules and uppercase mono labels adopted; §7's 13 px body and 15/18/22 px headings kept. |
| Placeholder researchers and institutions | — | Not shipped. |
