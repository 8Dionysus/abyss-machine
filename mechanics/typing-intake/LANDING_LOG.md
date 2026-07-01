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
- Saved-text state/write/status seam: `typing_saved_text_adapters` owns
  candidate processing, state document updates, state/latest/index write
  routing through supplied ports, and latest-status documents assembled from
  supplied latest/timer/service/age facts while CLI supplies concrete paths,
  live systemd reads, `typing_ingest`, and command rendering.
- WebExtension selftest runtime seam: `typing_browser_adapters` owns temporary
  Firefox profile prefs, `web-ext` command selection, loopback HTTP probe
  serving, temp profile/artifact/cache roots, subprocess lifecycle/cleanup,
  probe polling, and public-safe result assembly while latest/index writes and
  command rendering stay at the CLI edge.
- Native-host transport seam: `typing_browser_adapters` owns framed
  little-endian length-prefix message read/write, JSON decode/encode, and
  malformed-frame errors while CLI binds the adapter to real stdin/stdout,
  dispatches ingest, and renders the command exit.
- Firefox release-profile seam: `typing_browser_adapters` owns `profiles.ini`
  parsing, relative/absolute profile path projection, extension sidecar path
  projection, and release-profile selection while CLI supplies the configured
  profile file path and uses the selected profile inside live selftests.
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
  context inference callbacks, live probe orchestration, latest writes, and
  command rendering.
- AT-SPI path-targeted text/insert seam: `typing_atspi_adapters` owns
  `pyatspi` desktop loading, path resolution, URL/text-hash confirmation,
  accessibility focus, editable-text insert/set fallback, and result
  confirmation for a known AT-SPI path while CLI owns capture policy decisions,
  `typing_ingest`, latest writes, live probe orchestration, and command
  rendering.
- AT-SPI URL-scanned text/insert seam: `typing_atspi_adapters` owns GI Atspi
  loading, Firefox document scan/priority, URL/current-text hash confirmation,
  editable-text insert/set fallback, focus/caret handling, and after-hash
  confirmation while CLI owns capture policy decisions, `typing_ingest`,
  latest writes, live probe orchestration, and command rendering.
- AT-SPI frame-focus seam: `typing_atspi_adapters` owns GI Atspi loading,
  Firefox app/window scan, bounded title matching, component/action focus, and
  state confirmation while CLI owns capture policy decisions, `typing_ingest`,
  latest writes, live probe orchestration, and command rendering.
- AT-SPI selftest record-reader seam: `typing_atspi_adapters` owns
  browser/privacy selftest recent-record lookup by text hash or URL, bounded
  public-safe event projection, and absence-proof summaries while CLI owns the
  live history reader callback, latest writes, live probe orchestration, and
  command rendering.
- Browser-privacy selftest runtime seam: `typing_browser_adapters` owns the
  temporary Firefox login-sensitive loopback page, profile prep, subprocess
  lifecycle, metadata-event polling, focused metadata callback routing,
  absence-proof callback routing, redacted process tails, cleanup, and
  public-safe result document assembly while CLI owns policy reads, latest/index
  writes, callback binding, and command rendering.
- Browser selftest store seam: `typing_browser_adapters` owns browser selftest
  primary latest/history output, optional release-profile secondary output,
  typing-index refresh, and write-error projection through supplied write/index
  ports while CLI owns concrete paths, port binding, callbacks, policy reads,
  and command rendering.
