# config-templates Route

`config-templates/` owns public-safe source files that can be rendered into
`/etc/abyss-machine`.

Do not place rendered private configs, secrets, host captures, or live generated
facts here. Template placeholders should stay explicit and documented by the
bootstrap path.
