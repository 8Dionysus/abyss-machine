# Landing Log

- Initial skeleton: package created to route typing intake work.
- AT-SPI semantic seam: `typing_atspi_adapters` owns focused-snapshot
  ingest/document plans, text-event sample/metadata/debounce helpers, and
  generic GUI selftest documents while live `pyatspi` traversal/listeners stay
  at the CLI edge.
