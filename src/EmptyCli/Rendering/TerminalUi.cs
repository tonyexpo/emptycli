using System.Text;

namespace EmptyCli.Rendering;

/// <summary>
/// ANSI console surface with an alternate screen, a scrollable content area and a
/// fixed footer. In plain mode it degrades to a normal streaming writer.
/// </summary>
public sealed class TerminalUi : IDisposable
{
    private const int FooterBackground = 236;
    private readonly bool _color;
    private readonly bool _tui;
    private int _width;
    private int _height;
    private int _contentWidth;
    private EnvironmentInfo? _environment;
    private DateTime _lastFooter = DateTime.MinValue;
    private bool _disposed;

    public TerminalUi(CliOptions options)
    {
        _color = !options.NoColor
                 && !Console.IsOutputRedirected
                 && !string.Equals(Environment.GetEnvironmentVariable("TERM"), "dumb", StringComparison.OrdinalIgnoreCase);

        var canUseTui = !options.NoTui
                        && !Console.IsOutputRedirected
                        && !Console.IsInputRedirected;

        if (canUseTui && TryReadSize(out var width, out var height) && width >= 50 && height >= 10)
        {
            _tui = true;
            _width = width;
            _height = height;
            _contentWidth = Math.Max(30, width - 2);
        }
        else
        {
            _tui = false;
            _width = TryReadSize(out var fallbackWidth, out _) ? fallbackWidth : 100;
            _contentWidth = Math.Max(40, _width - 2);
        }
    }

    public bool IsTui => _tui;
    public int ContentWidth
    {
        get
        {
            if (_tui)
            {
                try
                {
                    if (Console.WindowWidth >= 40 && Console.WindowWidth != _width)
                    {
                        _width = Console.WindowWidth;
                        _contentWidth = Math.Max(30, _width - 2);
                    }
                }
                catch
                {
                    // Keep the last known width.
                }
            }

            return _contentWidth;
        }
    }

    public void Initialize(EnvironmentInfo environment)
    {
        _environment = environment;
        Console.Out.Flush();

        if (!_tui)
        {
            return;
        }

        try
        {
            Console.Out.Write("\x1b[?1049h"); // alternate screen
            Console.Out.Write("\x1b[?25l");   // hide cursor
            Console.Out.Write("\x1b[?7l");    // no autowrap: the renderer wraps manually
            Console.Out.Write("\x1b[2J\x1b[H");
            ApplyScrollRegion();
            Console.Out.Flush();
        }
        catch
        {
            // Fall back to plain streaming if the terminal refuses control sequences.
        }
    }

    public void ClearContent()
    {
        if (!_tui)
        {
            Console.Out.WriteLine();
            return;
        }

        Console.Out.Write("\x1b[2J\x1b[H");
        ApplyScrollRegion();
        Console.Out.Flush();
    }

    public string Style(string text, AnsiStyle style)
    {
        if (!_color || text.Length == 0 || style == default)
        {
            return text;
        }

        var builder = new StringBuilder(text.Length + 24);
        if (style.Bg is { } background)
        {
            builder.Append("\x1b[48;5;").Append(background).Append('m');
        }

        if (style.Fg is { } foreground)
        {
            builder.Append("\x1b[38;5;").Append(foreground).Append('m');
        }

        if (style.Bold)
        {
            builder.Append("\x1b[1m");
        }

        if (style.Dim)
        {
            builder.Append("\x1b[2m");
        }

        if (style.Italic)
        {
            builder.Append("\x1b[3m");
        }

        if (style.Underline)
        {
            builder.Append("\x1b[4m");
        }

        if (style.Strike)
        {
            builder.Append("\x1b[9m");
        }

        builder.Append(text);
        builder.Append("\x1b[0m");
        return builder.ToString();
    }

    public void Write(string text) => Console.Out.Write(text);

    public void WriteLine(string text = "")
    {
        Console.Out.Write(text);
        Console.Out.Write('\n');
    }

    public void RefreshFooter(SessionState state, PlaybackController controller, bool force = false)
    {
        if (!_tui || _environment is null)
        {
            return;
        }

        var now = DateTime.UtcNow;
        if (!force && (now - _lastFooter).TotalMilliseconds < 110)
        {
            return;
        }

        _lastFooter = now;

        try
        {
            if (Console.WindowWidth >= 40)
            {
                _width = Console.WindowWidth;
                _contentWidth = Math.Max(30, _width - 2);
            }

            DrawFooter(state, controller);
        }
        catch
        {
            // Never let a terminal hiccup break the replay.
        }
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;

        if (!_tui)
        {
            return;
        }

        try
        {
            Console.Out.Write("\x1b[0m");
            Console.Out.Write("\x1b[?7h");
            Console.Out.Write("\x1b[r");
            Console.Out.Write("\x1b[?25h");
            Console.Out.Write("\x1b[?1049l");
            Console.Out.Flush();
        }
        catch
        {
            // Ignore teardown failures.
        }
    }

    private void ApplyScrollRegion()
    {
        if (_height <= 2)
        {
            return;
        }

        Console.Out.Write($"\x1b[1;{_height - 1}r");
        Console.Out.Write("\x1b[1;1H");
    }

    private void DrawFooter(SessionState state, PlaybackController controller)
    {
        var width = Math.Max(40, _width);
        var left = new List<FooterSegment>
        {
            new("◆", Theme.Accent, Bold: true),
            new("emptycli", Theme.Text, Bold: true),
            new(FitPath(_environment!.ShortPath, 30), Theme.Path),
            new(_environment.Branch, Theme.Branch),
        };

        var modelName = ShortModelName(state.Meta);
        var right = new List<FooterSegment>
        {
            new(modelName, Theme.Model, Bold: true),
            new(state.FormatContext(), Theme.Muted),
            new(state.FormatCost(), Theme.Cost, Bold: true),
            new(state.FormatElapsed(controller.Elapsed), Theme.Muted),
        };

        if (Math.Abs(controller.Speed - 1) > 0.001)
        {
            right.Add(new($"×{controller.Speed:0.#}", Theme.Warn));
        }

        if (controller.Paused)
        {
            right.Add(new("⏸ paused", Theme.Warn, Bold: true));
        }

        while (VisibleLength(left, right) > width - 2)
        {
            if (!RemoveLowestPriorityFromRight(right))
            {
                if (!RemoveLowestPriorityFromLeft(left))
                {
                    break;
                }
            }
        }

        // Last resort: shrink the path to its folder name.
        var pathIndex = left.FindIndex(segment => segment.Color == Theme.Path);
        if (pathIndex >= 0 && VisibleLength(left, right) > width - 2)
        {
            left[pathIndex] = new FooterSegment(_environment.FolderName, Theme.Path);
        }

        var builder = new StringBuilder();
        builder.Append(Style(" ", new AnsiStyle(Bg: FooterBackground)));
        AppendSegments(builder, left);
        var used = 1 + SegmentsLength(left);
        var rightLength = SegmentsLength(right);
        var gap = Math.Max(2, width - used - rightLength - 1);
        builder.Append(Style(new string(' ', gap), new AnsiStyle(Bg: FooterBackground)));
        AppendSegments(builder, right);

        var totalVisible = used + gap + rightLength;
        if (totalVisible < width)
        {
            builder.Append(Style(new string(' ', width - totalVisible), new AnsiStyle(Bg: FooterBackground)));
        }

        Console.Out.Write("\u001b7");
        Console.Out.Write($"\x1b[{_height};1H");
        Console.Out.Write(builder.ToString());
        Console.Out.Write("\u001b8");
        Console.Out.Flush();
    }

    private void AppendSegments(StringBuilder builder, List<FooterSegment> segments)
    {
        for (var index = 0; index < segments.Count; index++)
        {
            if (index > 0)
            {
                builder.Append(Style("  ", new AnsiStyle(Bg: FooterBackground)));
            }

            var segment = segments[index];
            builder.Append(Style(segment.Text, new AnsiStyle(
                Fg: segment.Color,
                Bg: FooterBackground,
                Bold: segment.Bold)));
        }
    }

    private static int SegmentsLength(List<FooterSegment> segments)
    {
        var length = Math.Max(0, segments.Count - 1) * 2;
        foreach (var segment in segments)
        {
            length += segment.Text.Length;
        }

        return length;
    }

    private static int VisibleLength(List<FooterSegment> left, List<FooterSegment> right) =>
        SegmentsLength(left) + SegmentsLength(right) + 3;

    private bool RemoveLowestPriorityFromRight(List<FooterSegment> right)
    {
        // Context is the first thing to go, then the provider-less model name can shrink.
        var ctxIndex = right.FindIndex(segment => segment.Text.StartsWith("ctx ", StringComparison.Ordinal));
        if (ctxIndex >= 0)
        {
            right.RemoveAt(ctxIndex);
            return true;
        }

        var speedIndex = right.FindIndex(segment => segment.Text.StartsWith('×'));
        if (speedIndex >= 0)
        {
            right.RemoveAt(speedIndex);
            return true;
        }

        return false;
    }

    private bool RemoveLowestPriorityFromLeft(List<FooterSegment> left)
    {
        var pathIndex = left.FindIndex(segment => segment.Color == Theme.Path);
        if (pathIndex >= 0)
        {
            var current = left[pathIndex];
            if (!string.Equals(current.Text, _environment!.FolderName, StringComparison.Ordinal))
            {
                left[pathIndex] = current with { Text = _environment.FolderName };
                return true;
            }

            left.RemoveAt(pathIndex);
            return true;
        }

        var branchIndex = left.FindIndex(segment => segment.Color == Theme.Branch);
        if (branchIndex >= 0)
        {
            left.RemoveAt(branchIndex);
            return true;
        }

        var appIndex = left.FindIndex(segment => segment.Text == "emptycli");
        if (appIndex >= 0)
        {
            left.RemoveAt(appIndex);
            return true;
        }

        return false;
    }

    private static string FitPath(string path, int maxLength)
    {
        if (path.Length <= maxLength)
        {
            return path;
        }

        var parts = path.Split('/', StringSplitOptions.RemoveEmptyEntries);
        var result = parts.Length > 0 ? parts[^1] : path;
        for (var index = parts.Length - 2; index >= 0; index--)
        {
            var candidate = "…/" + string.Join('/', parts[index..]);
            if (candidate.Length > maxLength)
            {
                break;
            }

            result = candidate;
        }

        return result.Length <= maxLength ? result : result[^maxLength..];
    }

    private static string ShortModelName(Replay.ReplayMeta meta)
    {
        if (!string.IsNullOrWhiteSpace(meta.ModelName))
        {
            return meta.ModelName;
        }

        var slash = meta.Model.IndexOf('/');
        return slash >= 0 ? meta.Model[(slash + 1)..] : meta.Model;
    }

    private static bool TryReadSize(out int width, out int height)
    {
        try
        {
            width = Console.WindowWidth;
            height = Console.WindowHeight;
            return width > 0 && height > 0;
        }
        catch
        {
            width = 100;
            height = 30;
            return false;
        }
    }

    private readonly record struct FooterSegment(string Text, int Color, bool Bold = false);
}

public static class Theme
{
    public const int Text = 252;
    public const int Dim = 245;
    public const int Muted = 240;
    public const int Accent = 81;
    public const int Accent2 = 177;
    public const int Green = 114;
    public const int Red = 203;
    public const int Warn = 221;
    public const int Blue = 75;
    public const int Code = 180;
    public const int Path = 180;
    public const int Branch = 141;
    public const int Model = 177;
    public const int Cost = 114;
    public const int User = 114;
    public const int Orange = 215;
}
