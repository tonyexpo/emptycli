namespace EmptyCli.Rendering;

public readonly record struct AnsiStyle(
    int? Fg = null,
    int? Bg = null,
    bool Bold = false,
    bool Dim = false,
    bool Italic = false,
    bool Underline = false,
    bool Strike = false);
