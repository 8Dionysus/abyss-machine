"""Non-device organs staged outside the abyss_machine core.

abyss-machine is the grafting layer: device drivers, OS surfaces, desktop
adapters, raw sensors and trust parts stay in the core package. Organs here
are reasoning, memory/knowledge, AI runtime, release and application layers
on top of those capabilities; they load lazily through `abyss_machine.cli`
and are candidates to leave for their AbyssOS owner organs.
"""
