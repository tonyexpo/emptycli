using System.Text;
using EmptyCli.Replay;

namespace EmptyCli.Rendering;

public sealed class ReplayRenderer
{
    private readonly TerminalUi _ui;
    private readonly PlaybackController _controller;
    private readonly EnvironmentInfo _environment;
    private readonly MarkdownRenderer _markdown;
    private SessionState? _state;

    public ReplayRenderer(TerminalUi ui, PlaybackController controller, EnvironmentInfo environment)
    {
        _ui = ui;
        _controller = controller;
        _environment = environment;
        _markdown = new MarkdownRenderer(ui, controller, Tick);
    }

    public void BeginSession(SessionState state, int loopNumber)
    {
        _state = state;
        _ui.ClearContent();
        DrawBanner(state, loopNumber);
        _ui.RefreshFooter(state, _controller, force: true);
    }

    public void Tick() => Tick(force: false);

    public void Tick(bool force)
    {
        if (_state is null)
        {
            return;
        }

        _ui.RefreshFooter(_state, _controller, force);
    }

    public void Render(ReplayEvent replayEvent, SessionState state)
    {
        _state = state;
        switch (replayEvent.Kind)
        {
            case "phase":
                DrawPhase(replayEvent.Text ?? "");
                break;
            case "user":
                DrawUser(replayEvent.Text ?? "");
                break;
            case "think":
                DrawThinking(replayEvent);
                break;
            case "say":
                DrawAssistant(replayEvent);
                break;
            case "tool":
                DrawTool(replayEvent, state);
                break;
            case "line":
                DrawLine(replayEvent.Text ?? "", replayEvent.Style ?? "plain");
                break;
            case "todo":
                DrawTodos(replayEvent);
                break;
            case "note":
                DrawNote(replayEvent);
                break;
            case "usage":
                break;
            default:
                if (!string.IsNullOrEmpty(replayEvent.Text))
                {
                    DrawLine(replayEvent.Text, replayEvent.Style ?? "plain");
                }

                break;
        }
    }

    public void EndSession(SessionState state, bool once)
    {
        _ui.WriteLine();
        _ui.WriteLine("  " + _ui.Style(new string('─', Math.Min(64, Math.Max(20, _ui.ContentWidth - 4))),
            new AnsiStyle(Fg: Theme.Muted)));
        _ui.WriteLine("  " + _ui.Style("✓ replay complete", new AnsiStyle(Fg: Theme.Green, Bold: true))
                       + _ui.Style($"  {state.FormatElapsed(_controller.Elapsed)} · {state.FormatCost()} · " +
                                  $"{FormatTokens(state.InputTokens + state.OutputTokens)} tokens",
                           new AnsiStyle(Fg: Theme.Dim)));

        if (!string.IsNullOrWhiteSpace(state.Meta.Outro))
        {
            _ui.WriteLine("  " + _ui.Style(state.Meta.Outro, new AnsiStyle(Fg: Theme.Text)));
        }

        if (!string.IsNullOrWhiteSpace(state.Meta.OutroUrl))
        {
            _ui.WriteLine("  " + _ui.Style(state.Meta.OutroUrl, new AnsiStyle(Fg: Theme.Blue, Underline: true)));
        }

        _ui.WriteLine("  " + _ui.Style(
            once
                ? "exiting · thanks for watching"
                : "next session starts in 6s  ·  space pause  ·  r restart  ·  q quit",
            new AnsiStyle(Fg: Theme.Muted)));
    }

    private void DrawBanner(SessionState state, int loopNumber)
    {
        var tux = new[]
        {
            "   .--.",
            "  |o_o |",
            "  |:_/ |",
            " //   \\ \\",
            "(|     | )",
            "/'\\_   _/`\\",
            "\\___)=(___/",
        };

        foreach (var line in tux)
        {
            _ui.WriteLine("  " + _ui.Style(line, new AnsiStyle(Fg: Theme.Accent, Dim: true)));
        }

        _ui.WriteLine();
        _ui.WriteLine("  " + _ui.Style("emptycli", new AnsiStyle(Fg: Theme.Text, Bold: true))
                       + _ui.Style($" {_environment.Version}", new AnsiStyle(Fg: Theme.Muted))
                       + _ui.Style("  ·  agent replay", new AnsiStyle(Fg: Theme.Dim)));
        BannerField("session", state.SessionId, state.Meta.Title, Theme.Accent, Theme.Dim);
        BannerField("model", state.Meta.Model, state.Meta.ModelName, Theme.Model, Theme.Muted, bold: true);
        BannerField("project", state.Meta.Project, state.Meta.Description, Theme.Text, Theme.Dim, bold: true);
        BannerField("cwd", _environment.ShortPath, $"({_environment.Branch})", Theme.Path, Theme.Branch);
        _ui.WriteLine("  " + Label("keys") + _ui.Style("space pause  ·  +/- speed  ·  r restart  ·  q quit",
            new AnsiStyle(Fg: Theme.Muted)));
        _ui.WriteLine("  " + _ui.Style(new string('─', Math.Min(72, Math.Max(20, _ui.ContentWidth - 4))),
            new AnsiStyle(Fg: Theme.Muted)));
        _ui.WriteLine();
    }

    private void DrawPhase(string text)
    {
        var elapsed = _controller.Elapsed;
        var timestamp = $"{(int)elapsed.TotalMinutes:00}:{elapsed.Seconds:00}";
        var remaining = Math.Max(0, _ui.ContentWidth - timestamp.Length - text.Length - 8);
        _ui.WriteLine();
        _ui.WriteLine("  " + _ui.Style(timestamp, new AnsiStyle(Fg: Theme.Muted))
                       + "  " + _ui.Style("── " + text + " ", new AnsiStyle(Fg: Theme.Accent, Bold: true))
                       + _ui.Style(new string('─', Math.Min(remaining, 140)), new AnsiStyle(Fg: Theme.Muted)));
        _ui.WriteLine();
    }

    private void DrawUser(string text)
    {
        _ui.WriteLine();
        _ui.WriteLine("  " + _ui.Style("▌ you", new AnsiStyle(Fg: Theme.User, Bold: true)));
        var width = Math.Max(20, _ui.ContentWidth - 6);
        foreach (var paragraph in text.Replace("\r\n", "\n").Split('\n'))
        {
            foreach (var line in WrapPlain(paragraph, width))
            {
                _ui.WriteLine("  " + _ui.Style("┃ ", new AnsiStyle(Fg: Theme.User))
                                   + _ui.Style(line, new AnsiStyle(Fg: Theme.Text)));
            }
        }

        _ui.WriteLine();
    }

    private void DrawThinking(ReplayEvent replayEvent)
    {
        _ui.WriteLine();
        _ui.WriteLine("  " + _ui.Style("✻ Thinking", new AnsiStyle(Fg: Theme.Accent2, Bold: true, Dim: true)));
        _markdown.Render(
            replayEvent.Text ?? "",
            new AnsiStyle(Fg: Theme.Dim, Italic: true),
            Theme.Accent2,
            replayEvent.Ms);
    }

    private void DrawAssistant(ReplayEvent replayEvent)
    {
        _ui.WriteLine();
        _markdown.Render(
            replayEvent.Text ?? "",
            new AnsiStyle(Fg: Theme.Text),
            Theme.Accent,
            replayEvent.Ms);
    }

    private void DrawTool(ReplayEvent replayEvent, SessionState state)
    {
        var tool = (replayEvent.Tool ?? "tool").ToLowerInvariant();
        var isBash = tool == "bash";

        var segments = new List<Segment>
        {
            new("  ", default),
            new(isBash ? "$" : "→", new AnsiStyle(Fg: isBash ? Theme.Orange : Theme.Accent, Bold: true)),
            new(" ", default),
        };

        if (isBash)
        {
            segments.Add(new(Truncate(replayEvent.Arg ?? "", 90), new AnsiStyle(Fg: Theme.Text, Bold: true)));
        }
        else
        {
            segments.Add(new(ToolLabel(tool), new AnsiStyle(Fg: Theme.Text, Bold: true)));
            if (!string.IsNullOrWhiteSpace(replayEvent.Arg))
            {
                segments.Add(new(" ", default));
                segments.Add(new(ShortenMiddle(replayEvent.Arg!, Math.Max(24, _ui.ContentWidth - 34)),
                    new AnsiStyle(Fg: Theme.Path)));
            }
        }

        if (!string.IsNullOrWhiteSpace(replayEvent.Detail))
        {
            segments.Add(new("  · " + replayEvent.Detail, new AnsiStyle(Fg: Theme.Dim)));
        }

        if (replayEvent.Additions > 0 || replayEvent.Deletions > 0)
        {
            segments.Add(new("  ", default));
            segments.Add(new($"+{replayEvent.Additions}", new AnsiStyle(Fg: Theme.Green)));
            segments.Add(new(" ", default));
            segments.Add(new($"−{replayEvent.Deletions}", new AnsiStyle(Fg: Theme.Red)));
        }

        if (string.Equals(replayEvent.Status, "running", StringComparison.OrdinalIgnoreCase))
        {
            _ui.WriteLine(Compose(segments, _ui.ContentWidth));
            return;
        }

        var ok = !string.Equals(replayEvent.Status, "error", StringComparison.OrdinalIgnoreCase);
        var duration = FormatDuration(replayEvent.Ms);
        var finalSegments = new List<Segment>(segments);
        finalSegments.Add(new("  ", default));
        finalSegments.Add(new(ok ? "✓" : "✗", new AnsiStyle(Fg: ok ? Theme.Green : Theme.Red, Bold: true)));
        if (!string.IsNullOrEmpty(duration))
        {
            finalSegments.Add(new(" " + duration, new AnsiStyle(Fg: Theme.Muted)));
        }

        if (_ui.IsTui && replayEvent.Ms >= 250 && !_controller.QuitRequested)
        {
            SpinTool(segments, finalSegments, replayEvent.Ms);
        }
        else
        {
            _ui.WriteLine(Compose(finalSegments, _ui.ContentWidth));
        }

        _ui.RefreshFooter(state, _controller);
    }

    private void SpinTool(List<Segment> baseSegments, List<Segment> finalSegments, double milliseconds)
    {
        var frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏";
        var total = milliseconds / Math.Max(0.05, _controller.Speed);
        var start = _controller.Elapsed;
        var frame = 0;

        while (!_controller.QuitRequested)
        {
            var elapsed = (_controller.Elapsed - start).TotalMilliseconds;
            if (elapsed >= total)
            {
                break;
            }

            var spinning = new List<Segment>(baseSegments)
            {
                new("  ", default),
                new(frames[frame++ % frames.Length].ToString(), new AnsiStyle(Fg: Theme.Accent)),
            };
            _ui.Write("\r" + Compose(spinning, _ui.ContentWidth) + "\x1b[K");
            _controller.DelayMs(70, Tick);
        }

        _ui.Write("\r" + Compose(finalSegments, _ui.ContentWidth) + "\x1b[K\n");
    }

    private void DrawLine(string text, string style)
    {
        var diff = style is "add" or "del" or "hunk" or "ctx";
        var indent = diff || style is "output" or "out" ? 4 : 2;
        var available = Math.Max(10, _ui.ContentWidth - indent);
        var line = Truncate(text.Replace("\t", "    "), available);
        var ansi = style switch
        {
            "add" => new AnsiStyle(Fg: Theme.Green),
            "del" => new AnsiStyle(Fg: Theme.Red),
            "hunk" => new AnsiStyle(Fg: Theme.Accent),
            "ctx" => new AnsiStyle(Fg: Theme.Dim),
            "output" or "out" => new AnsiStyle(Fg: Theme.Dim),
            "muted" => new AnsiStyle(Fg: Theme.Muted),
            "ok" => new AnsiStyle(Fg: Theme.Green),
            "err" => new AnsiStyle(Fg: Theme.Red),
            "warn" => new AnsiStyle(Fg: Theme.Warn),
            "accent" => new AnsiStyle(Fg: Theme.Accent),
            "bold" => new AnsiStyle(Fg: Theme.Text, Bold: true),
            "code" => new AnsiStyle(Fg: Theme.Code),
            "path" => new AnsiStyle(Fg: Theme.Path),
            "rule" => new AnsiStyle(Fg: Theme.Muted),
            "heading" => new AnsiStyle(Fg: Theme.Accent, Bold: true),
            "user" => new AnsiStyle(Fg: Theme.User),
            _ => new AnsiStyle(Fg: Theme.Text),
        };

        _ui.WriteLine(new string(' ', indent) + _ui.Style(line, ansi));
    }

    private void DrawTodos(ReplayEvent replayEvent)
    {
        if (replayEvent.Todos is { Count: > 0 })
        {
            var completed = replayEvent.Todos.Count(todo => todo.Status == "completed");
            _ui.WriteLine();
            _ui.WriteLine("  " + _ui.Style("◐ Todos", new AnsiStyle(Fg: Theme.Accent, Bold: true))
                           + _ui.Style($"  {completed}/{replayEvent.Todos.Count}", new AnsiStyle(Fg: Theme.Muted)));
            foreach (var todo in replayEvent.Todos)
            {
                var (icon, iconStyle, textStyle) = todo.Status switch
                {
                    "completed" => ("✓", new AnsiStyle(Fg: Theme.Green, Bold: true),
                        new AnsiStyle(Fg: Theme.Muted, Strike: true)),
                    "in_progress" => ("▸", new AnsiStyle(Fg: Theme.Warn, Bold: true),
                        new AnsiStyle(Fg: Theme.Text)),
                    _ => ("○", new AnsiStyle(Fg: Theme.Muted),
                        new AnsiStyle(Fg: Theme.Dim)),
                };
                _ui.WriteLine("  " + _ui.Style(icon, iconStyle) + " " + _ui.Style(todo.Text, textStyle));
            }
        }
        else if (!string.IsNullOrWhiteSpace(replayEvent.Text))
        {
            _ui.WriteLine("  " + _ui.Style("▸", new AnsiStyle(Fg: Theme.Accent, Bold: true))
                               + " " + _ui.Style(replayEvent.Text, new AnsiStyle(Fg: Theme.Dim)));
        }
    }

    private void DrawNote(ReplayEvent replayEvent)
    {
        var style = replayEvent.Style switch
        {
            "warn" => new AnsiStyle(Fg: Theme.Warn),
            "ok" => new AnsiStyle(Fg: Theme.Green),
            _ => new AnsiStyle(Fg: Theme.Dim),
        };

        _ui.WriteLine("  " + _ui.Style("◆", new AnsiStyle(Fg: Theme.Blue))
                           + " " + _ui.Style(replayEvent.Text ?? "", style));
    }

    private string Label(string text) =>
        _ui.Style(text.PadRight(9), new AnsiStyle(Fg: Theme.Muted));

    private void BannerField(string label, string value, string? suffix, int valueColor, int suffixColor, bool bold = false)
    {
        var available = Math.Max(12, _ui.ContentWidth - 11);
        if (!string.IsNullOrWhiteSpace(suffix))
        {
            var combined = value + "  ·  " + suffix;
            if (combined.Length <= available)
            {
                _ui.WriteLine("  " + Label(label)
                                   + _ui.Style(value, new AnsiStyle(Fg: valueColor, Bold: bold))
                                   + _ui.Style("  ·  " + suffix, new AnsiStyle(Fg: suffixColor)));
                return;
            }
        }

        _ui.WriteLine("  " + Label(label) + _ui.Style(Truncate(value, available), new AnsiStyle(Fg: valueColor, Bold: bold)));
    }

    private string Compose(List<Segment> segments, int maxWidth)
    {
        var builder = new StringBuilder();
        var used = 0;
        foreach (var segment in segments)
        {
            if (used >= maxWidth)
            {
                break;
            }

            var text = segment.Text;
            if (used + text.Length > maxWidth)
            {
                text = text[..(maxWidth - used)];
            }

            builder.Append(_ui.Style(text, segment.Style));
            used += text.Length;
        }

        return builder.ToString();
    }

    private static IEnumerable<string> WrapPlain(string text, int width)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            yield return "";
            yield break;
        }

        var words = text.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        var line = new StringBuilder();
        foreach (var word in words)
        {
            if (line.Length > 0 && line.Length + 1 + word.Length > width)
            {
                yield return line.ToString();
                line.Clear();
            }

            if (line.Length > 0)
            {
                line.Append(' ');
            }

            line.Append(word.Length > width ? word[..width] : word);
        }

        if (line.Length > 0)
        {
            yield return line.ToString();
        }
    }

    private static string ToolLabel(string tool) => tool switch
    {
        "read" => "Read",
        "write" => "Write",
        "edit" => "Edit",
        "glob" => "Glob",
        "grep" => "Grep",
        "fetch" => "Fetch",
        "task" => "Task",
        "browser" => "Browser",
        "list" => "List",
        "todo" => "Todo",
        _ => char.ToUpperInvariant(tool.Length > 0 ? tool[0] : '?') + tool[1..],
    };

    private static string FormatDuration(double milliseconds)
    {
        if (milliseconds <= 0)
        {
            return "";
        }

        if (milliseconds < 1000)
        {
            return $"{milliseconds / 1000:0.0}s";
        }

        var seconds = milliseconds / 1000;
        if (seconds < 10)
        {
            return $"{seconds:0.0}s";
        }

        if (seconds < 60)
        {
            return $"{seconds:0}s";
        }

        return $"{(int)(seconds / 60)}m {(int)(seconds % 60)}s";
    }

    private static string FormatTokens(long tokens) =>
        tokens >= 1000 ? $"{tokens / 1000d:0.#}k" : tokens.ToString();

    private static string ShortenMiddle(string value, int maxLength)
    {
        if (value.Length <= maxLength)
        {
            return value;
        }

        if (maxLength < 8)
        {
            return value[..maxLength];
        }

        var head = (maxLength - 1) / 2;
        var tail = maxLength - 1 - head;
        return value[..head] + "…" + value[^tail..];
    }

    private static string Truncate(string text, int max)
    {
        if (text.Length <= max)
        {
            return text;
        }

        return max <= 1 ? text[..max] : text[..(max - 1)] + "…";
    }

    private readonly record struct Segment(string Text, AnsiStyle Style);
}
