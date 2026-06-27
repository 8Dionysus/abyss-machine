# Landing Log

- Initial skeleton: package created to route typing intake work.
- AT-SPI semantic seam: `typing_atspi_adapters` owns focused-snapshot
  ingest/document plans, text-event sample/metadata/debounce helpers, and
  generic GUI selftest documents; later runtime seams continue splitting live
  `pyatspi` responsibilities from the CLI edge.
- Saved-text scan seam: `typing_saved_text_adapters` owns filesystem scan
  limits, path walking, state continuity, decode rejection, skip/candidate
  accounting, ingest kwargs, state entries, and public-safe scan documents
  while `typing_ingest`, state/latest writes, timer/service status, and command
  rendering stay at the CLI edge.
- WebExtension selftest runtime seam: `typing_browser_adapters` owns temporary
  Firefox profile prefs, `web-ext` command selection, loopback HTTP probe
  serving, temp profile/artifact/cache roots, subprocess lifecycle/cleanup,
  probe polling, and public-safe result assembly while latest/index writes and
  command rendering stay at the CLI edge.
- Native-host transport seam: `typing_browser_adapters` owns framed
  little-endian length-prefix message read/write, JSON decode/encode, and
  malformed-frame errors while CLI binds the adapter to real stdin/stdout,
  dispatches ingest, and renders the command exit.
- AT-SPI object-runtime seam: `typing_atspi_adapters` owns supplied-object
  state flags, text payload reads, object paths, document attributes,
  application/proc fallback context, and event object context projection while
  CLI still owns focused/browser accessibility traversal, ingest, latest
  writes, and command rendering.
- AT-SPI listener-runtime seam: `typing_atspi_adapters` owns `pyatspi` loading
  for text events, event type normalization, Registry register/start/stop,
  bounded sample timers, heartbeat refresh loops, max-event stop, summary
  counters, compact-history callback routing, and listener failure documents
  while CLI owns policy reads, `typing_ingest`, latest/history write callbacks,
  and command rendering.
- AT-SPI traversal-runtime seam: `typing_atspi_adapters` owns `pyatspi`
  desktop loading, timeout setup, safe child traversal, focused-candidate tree
  walk, path parsing/resolution, URL metadata focus traversal, and
  accessibility focus actions while CLI owns capture policy decisions, browser
  context inference callbacks, GI/Atspi frame focus, live probe orchestration,
  latest writes, and command rendering.
- AT-SPI path-targeted text/insert seam: `typing_atspi_adapters` owns
  `pyatspi` desktop loading, path resolution, URL/text-hash confirmation,
  accessibility focus, editable-text insert/set fallback, and result
  confirmation for a known AT-SPI path while CLI owns capture policy decisions,
  `typing_ingest`, latest writes, URL-scanned text insertion, GI/Atspi frame
  focus, live probe orchestration, and command rendering.
