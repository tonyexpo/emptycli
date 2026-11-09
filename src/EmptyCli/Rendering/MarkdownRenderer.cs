using System.Text;

namespace EmptyCli.Rendering;

/// <summary>
/// Small markdown-ish streamer. Supports headings, bullets, numbered lists,
/// fenced code blocks, bold, italics and inline code. Wrapping is manual so it
/// stays correct in the no-autowrap TUI.
/// </summary>
public sealed class MarkdownRenderer
{
    private readonly TerminalUi _ui;
    private readonly PlaybackController _controller;
    private readonly Action _tick;

    public MarkdownRenderer(TerminalUi ui, PlaybackController controller, Action tick)
    {
        _ui = ui;
        _controller = controller;
        _tick = tick;
    }

    public void Render(string text, AnsiStyle baseStyle, int headingColor, double durationMs)
    {
        var blocks = Parse(text);
        var visibleChars = CountVisibleChars(blocks);
        var perCharMs = visibleChars > 0 && durationMs > 0 ? durationMs / visibleChars : 0;

        foreach (var block in blocks)
        {
            if (_controller.QuitRequested)
            {
                return;
            }

            switch (block.Kind)
            {
                case BlockKind.Blank:
                    _ui.WriteLine();
                    break;

                case BlockKind.Rule:
                    PrintRule();
                    break;

                case BlockKind.Code:
                    PrintCode(block.CodeLines, perCharMs);
                    break;

                default:
                    PrintTextBlock(block, baseStyle, headingColor, perCharMs);
                    break;
            }
        }
    }

    private void PrintTextBlock(Block block, AnsiStyle baseStyle, int headingColor, double perCharMs)
    {
        var indent = 2;
        var hanging = block.Kind switch
        {
            BlockKind.Bullet => 2,
            BlockKind.Numbered => block.Prefix.Length + 1,
            _ => 0,
        };

        var width = Math.Max(12, _ui.ContentWidth - indent - hanging);
        var runs = ResolveInline(block.Runs, baseStyle);
        var lines = Wrap(runs, width);
        if (lines.Count == 0)
        {
            _ui.WriteLine();
            return;
        }

        var headingStyle = block.Kind switch
        {
            BlockKind.Heading1 => new AnsiStyle(Fg: headingColor, Bold: true),
            BlockKind.Heading2 => new AnsiStyle(Fg: Theme.Accent2, Bold: true),
            BlockKind.Heading3 => new AnsiStyle(Fg: Theme.Text, Bold: true),
            _ => baseStyle,
        };

        for (var lineIndex = 0; lineIndex < lines.Count; lineIndex++)
        {
            if (_controller.QuitRequested)
            {
                return;
            }

            if (block.Kind is BlockKind.Heading1 or BlockKind.Heading2 or BlockKind.Heading3)
            {
                _ui.Write(new string(' ', indent));
            }
            else
            {
                _ui.Write(new string(' ', indent));
                if (lineIndex == 0)
                {
                    if (block.Kind == BlockKind.Bullet)
                    {
                        _ui.Write(_ui.Style("• ", new AnsiStyle(Fg: Theme.Accent, Bold: true)));
                    }
                    else if (block.Kind == BlockKind.Numbered)
                    {
                        _ui.Write(_ui.Style(block.Prefix + " ", new AnsiStyle(Fg: Theme.Accent)));
                    }
                }
                else if (hanging > 0)
                {
                    _ui.Write(new string(' ', hanging));
                }
            }

            var line = lines[lineIndex];
            for (var wordIndex = 0; wordIndex < line.Count; wordIndex++)
            {
                var word = line[wordIndex];
                var isHeading = block.Kind is BlockKind.Heading1 or BlockKind.Heading2 or BlockKind.Heading3;

                foreach (var piece in word.Pieces)
                {
                    _ui.Write(_ui.Style(piece.Text, isHeading ? headingStyle : piece.Style));
                }

                if (wordIndex < line.Count - 1)
                {
                    _ui.Write(" ");
                }

                if (perCharMs > 0)
                {
                    var delay = Math.Min(140, (word.Length + 1) * perCharMs);
                    _controller.DelayMs(delay, _tick);
                    if (_controller.QuitRequested)
                    {
                        _ui.WriteLine();
                        return;
                    }
                }
            }

            _ui.WriteLine();
        }
    }

    private void PrintCode(List<string> lines, double perCharMs)
    {
        var available = Math.Max(12, _ui.ContentWidth - 6);
        foreach (var rawLine in lines)
        {
            if (_controller.QuitRequested)
            {
                return;
            }

            var line = Truncate(rawLine.Replace("\t", "    "), available);
            _ui.Write("  ");
            _ui.Write(_ui.Style("│ ", new AnsiStyle(Fg: Theme.Muted)));
            _ui.WriteLine(_ui.Style(line, new AnsiStyle(Fg: Theme.Code)));

            if (perCharMs > 0)
            {
                _controller.DelayMs(Math.Min(180, line.Length * perCharMs), _tick);
            }
        }
    }

    private void PrintRule()
    {
        var width = Math.Min(Math.Max(20, _ui.ContentWidth - 4), 64);
        _ui.WriteLine("  " + _ui.Style(new string('─', width), new AnsiStyle(Fg: Theme.Muted)));
    }

    private static List<List<Word>> Wrap(List<StyledRun> runs, int width)
    {
        var words = Tokenize(runs);
        var lines = new List<List<Word>>();
        var current = new List<Word>();
        var currentWidth = 0;

        foreach (var word in words)
        {
            if (word.Length > width)
            {
                if (current.Count > 0)
                {
                    lines.Add(current);
                    current = [];
                    currentWidth = 0;
                }

                lines.AddRange(ChunkWord(word, width));
                continue;
            }

            var needed = current.Count == 0 ? word.Length : word.Length + 1;
            if (currentWidth + needed > width && current.Count > 0)
            {
                lines.Add(current);
                current = [];
                currentWidth = 0;
                needed = word.Length;
            }

            current.Add(word);
            currentWidth += needed;
        }

        if (current.Count > 0)
        {
            lines.Add(current);
        }

        return lines;
    }

    private static List<Word> ChunkWord(Word word, int width)
    {
        var result = new List<Word>();
        var pieces = new List<Piece>();
        var length = 0;

        foreach (var piece in word.Pieces)
        {
            var remaining = piece.Text;
            while (remaining.Length > 0)
            {
                var take = Math.Min(width - length, remaining.Length);
                if (take > 0)
                {
                    pieces.Add(new Piece(remaining[..take], piece.Style));
                    length += take;
                    remaining = remaining[take..];
                }

                if (length == width)
                {
                    result.Add(new Word(pieces));
                    pieces = [];
                    length = 0;
                }
            }
        }

        if (pieces.Count > 0)
        {
            result.Add(new Word(pieces));
        }

        return result;
    }

    private static List<Word> Tokenize(List<StyledRun> runs)
    {
        var words = new List<Word>();
        List<Piece>? currentWord = null;
        StringBuilder? currentPiece = null;
        AnsiStyle? currentStyle = null;

        void FlushPiece()
        {
            if (currentPiece is null || currentPiece.Length == 0)
            {
                return;
            }

            currentWord ??= [];
            currentWord.Add(new Piece(currentPiece.ToString(), currentStyle!.Value));
            currentPiece.Clear();
        }

        void FlushWord()
        {
            FlushPiece();
            if (currentWord is { Count: > 0 })
            {
                words.Add(new Word(currentWord));
                currentWord = null;
            }
        }

        foreach (var run in runs)
        {
            foreach (var character in run.Text)
            {
                if (character == ' ')
                {
                    FlushWord();
                    currentStyle = null;
                    continue;
                }

                if (currentStyle != run.Style)
                {
                    FlushPiece();
                    currentStyle = run.Style;
                }

                currentPiece ??= new StringBuilder();
                currentPiece.Append(character);
            }
        }

        FlushWord();
        return words;
    }

    private static List<StyledRun> ResolveInline(List<InlineRun> runs, AnsiStyle baseStyle)
    {
        var styled = new List<StyledRun>(runs.Count);
        foreach (var run in runs)
        {
            var style = run.Kind switch
            {
                InlineKind.Bold => baseStyle with { Bold = true },
                InlineKind.Italic => baseStyle with { Italic = true },
                InlineKind.Code => new AnsiStyle(Fg: Theme.Code, Bg: 236),
                InlineKind.Link => new AnsiStyle(Fg: Theme.Blue, Underline: true),
                _ => baseStyle,
            };
            styled.Add(new StyledRun(run.Text, style));
        }

        return styled;
    }

    private static int CountVisibleChars(List<Block> blocks)
    {
        var count = 0;
        foreach (var block in blocks)
        {
            if (block.CodeLines.Count > 0)
            {
                count += block.CodeLines.Sum(line => line.Length);
                continue;
            }

            if (block.Kind == BlockKind.Rule)
            {
                count += 20;
                continue;
            }

            foreach (var run in block.Runs)
            {
                count += run.Text.Length;
            }

            count += block.Prefix.Length;
        }

        return count;
    }

    private static List<Block> Parse(string text)
    {
        var normalized = text.Replace("\r\n", "\n").Replace('\r', '\n');
        var lines = normalized.Split('\n');
        var blocks = new List<Block>();
        var paragraph = new List<string>();
        var codeLines = new List<string>();
        var inCode = false;
        string? codeLanguage = null;

        void FlushParagraph()
        {
            if (paragraph.Count == 0)
            {
                return;
            }

            var joined = string.Join(" ", paragraph.Select(line => line.Trim())).Trim();
            paragraph.Clear();
            if (joined.Length > 0)
            {
                blocks.Add(new Block(BlockKind.Paragraph, "", ParseInline(joined), [], null));
            }
        }

        foreach (var rawLine in lines)
        {
            var line = rawLine.TrimEnd();
            var trimmed = line.TrimStart();

            if (inCode)
            {
                if (trimmed.StartsWith("```", StringComparison.Ordinal))
                {
                    blocks.Add(new Block(BlockKind.Code, "", [], [.. codeLines], codeLanguage));
                    codeLines.Clear();
                    inCode = false;
                    codeLanguage = null;
                }
                else
                {
                    codeLines.Add(line);
                }

                continue;
            }

            if (trimmed.StartsWith("```", StringComparison.Ordinal))
            {
                FlushParagraph();
                inCode = true;
                codeLanguage = trimmed[3..].Trim();
                continue;
            }

            if (trimmed.Length == 0)
            {
                FlushParagraph();
                if (blocks.Count == 0 || blocks[^1].Kind != BlockKind.Blank)
                {
                    blocks.Add(new Block(BlockKind.Blank, "", [], [], null));
                }

                continue;
            }

            if (trimmed is "---" or "***" or "___")
            {
                FlushParagraph();
                blocks.Add(new Block(BlockKind.Rule, "", [], [], null));
                continue;
            }

            if (trimmed.StartsWith('#'))
            {
                var level = 0;
                while (level < trimmed.Length && level < 3 && trimmed[level] == '#')
                {
                    level++;
                }

                if (level > 0 && level < trimmed.Length && trimmed[level] == ' ')
                {
                    FlushParagraph();
                    var heading = trimmed[(level + 1)..].Trim();
                    var kind = level switch
                    {
                        1 => BlockKind.Heading1,
                        2 => BlockKind.Heading2,
                        _ => BlockKind.Heading3,
                    };
                    blocks.Add(new Block(kind, "", ParseInline(heading), [], null));
                    continue;
                }
            }

            if (trimmed.StartsWith("- ", StringComparison.Ordinal) ||
                trimmed.StartsWith("* ", StringComparison.Ordinal))
            {
                FlushParagraph();
                blocks.Add(new Block(BlockKind.Bullet, "•", ParseInline(trimmed[2..]), [], null));
                continue;
            }

            var numberedLength = NumberedPrefixLength(trimmed);
            if (numberedLength > 0)
            {
                FlushParagraph();
                var prefix = trimmed[..numberedLength];
                blocks.Add(new Block(BlockKind.Numbered, prefix, ParseInline(trimmed[numberedLength..].TrimStart()), [], null));
                continue;
            }

            paragraph.Add(trimmed);
        }

        FlushParagraph();
        if (inCode && codeLines.Count > 0)
        {
            blocks.Add(new Block(BlockKind.Code, "", [], [.. codeLines], codeLanguage));
        }

        return blocks;
    }

    private static int NumberedPrefixLength(string line)
    {
        var index = 0;
        while (index < line.Length && char.IsDigit(line[index]))
        {
            index++;
        }

        if (index > 0 && index + 1 < line.Length && line[index] == '.' && line[index + 1] == ' ')
        {
            return index + 1;
        }

        return 0;
    }

    private static List<InlineRun> ParseInline(string text)
    {
        var runs = new List<InlineRun>();
        var buffer = new StringBuilder();

        void Flush()
        {
            if (buffer.Length > 0)
            {
                runs.Add(new InlineRun(buffer.ToString(), InlineKind.Normal));
                buffer.Clear();
            }
        }

        for (var index = 0; index < text.Length; index++)
        {
            var current = text[index];

            if (current == '`')
            {
                var end = text.IndexOf('`', index + 1);
                if (end > index + 1)
                {
                    Flush();
                    runs.Add(new InlineRun(text[(index + 1)..end], InlineKind.Code));
                    index = end;
                    continue;
                }
            }

            if (current == '*' && index + 1 < text.Length && text[index + 1] == '*')
            {
                var end = text.IndexOf("**", index + 2, StringComparison.Ordinal);
                if (end > index + 2)
                {
                    Flush();
                    runs.Add(new InlineRun(text[(index + 2)..end], InlineKind.Bold));
                    index = end + 1;
                    continue;
                }
            }

            if (current == '*' && index + 1 < text.Length && text[index + 1] != ' ')
            {
                var end = text.IndexOf('*', index + 1);
                if (end > index + 1)
                {
                    Flush();
                    runs.Add(new InlineRun(text[(index + 1)..end], InlineKind.Italic));
                    index = end;
                    continue;
                }
            }

            if (current == '[')
            {
                var close = text.IndexOf(']', index + 1);
                if (close > index + 1 && close + 1 < text.Length && text[close + 1] == '(')
                {
                    var end = text.IndexOf(')', close + 2);
                    if (end > close + 1)
                    {
                        Flush();
                        runs.Add(new InlineRun(text[(index + 1)..close], InlineKind.Link));
                        index = end;
                        continue;
                    }
                }
            }

            buffer.Append(current);
        }

        Flush();
        return runs;
    }

    private static string Truncate(string text, int max)
    {
        if (text.Length <= max)
        {
            return text;
        }

        return max <= 1 ? text[..max] : text[..(max - 1)] + "…";
    }

    private enum BlockKind
    {
        Paragraph,
        Bullet,
        Numbered,
        Heading1,
        Heading2,
        Heading3,
        Code,
        Rule,
        Blank,
    }

    private enum InlineKind
    {
        Normal,
        Bold,
        Italic,
        Code,
        Link,
    }

    private sealed record Block(
        BlockKind Kind,
        string Prefix,
        List<InlineRun> Runs,
        List<string> CodeLines,
        string? Language);

    private sealed record InlineRun(string Text, InlineKind Kind);

    private sealed record StyledRun(string Text, AnsiStyle Style);

    private sealed record Piece(string Text, AnsiStyle Style);

    private sealed record Word(List<Piece> Pieces)
    {
        public int Length => Pieces.Sum(piece => piece.Text.Length);
    }
}
