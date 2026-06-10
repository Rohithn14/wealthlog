# Bundled fonts

`DejaVuSans.ttf` and `DejaVuSans-Bold.ttf` are from the **DejaVu Fonts** project
(<https://dejavu-fonts.github.io/>). They are embedded (subset) into generated PDF
reports so the Indian Rupee sign `₹` (U+20B9) and other Unicode glyphs render
correctly, which the latin-1 core PDF fonts cannot do.

DejaVu fonts are released under a permissive Bitstream Vera / DejaVu license
(free to use, embed, and redistribute). See the upstream `LICENSE` for full terms.
