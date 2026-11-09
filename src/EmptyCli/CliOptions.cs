namespace EmptyCli;

public sealed class CliOptions
{
    public const string Version = "0.1.0";

    public double Speed { get; private set; } = 1.0;
    public bool Once { get; private set; }
    public bool NoTui { get; private set; }
    public bool NoColor { get; private set; }
    public string? ReplayPath { get; private set; }
    public bool ShowHelp { get; private set; }
    public bool ShowVersion { get; private set; }
    public string? Error { get; private set; }

    public static CliOptions Parse(string[] args)
    {
        var options = new CliOptions();

        for (var index = 0; index < args.Length; index++)
        {
            var arg = args[index];

            switch (arg)
            {
                case "-h":
                case "--help":
                    options.ShowHelp = true;
                    break;

                case "-v":
                case "--version":
                    options.ShowVersion = true;
                    break;

                case "--once":
                    options.Once = true;
                    break;

                case "--no-tui":
                    options.NoTui = true;
                    break;

                case "--no-color":
                    options.NoColor = true;
                    break;

                case "--speed":
                    if (!TryReadValue(args, ref index, out var speedValue, options))
                    {
                        return options;
                    }

                    if (!double.TryParse(speedValue, System.Globalization.NumberStyles.Float,
                            System.Globalization.CultureInfo.InvariantCulture, out var speed) ||
                        speed < 0.05 || speed > 1000)
                    {
                        options.Error = $"--speed expects a number between 0.05 and 1000, got '{speedValue}'.";
                        return options;
                    }

                    options.Speed = speed;
                    break;

                case "--replay":
                    if (!TryReadValue(args, ref index, out var replayValue, options))
                    {
                        return options;
                    }

                    options.ReplayPath = replayValue;
                    break;

                default:
                    if (arg.StartsWith("--speed=", StringComparison.Ordinal))
                    {
                        var value = arg["--speed=".Length..];
                        if (!double.TryParse(value, System.Globalization.NumberStyles.Float,
                                System.Globalization.CultureInfo.InvariantCulture, out var parsedSpeed) ||
                            parsedSpeed < 0.05 || parsedSpeed > 1000)
                        {
                            options.Error = $"--speed expects a number between 0.05 and 1000, got '{value}'.";
                            return options;
                        }

                        options.Speed = parsedSpeed;
                    }
                    else if (arg.StartsWith("--replay=", StringComparison.Ordinal))
                    {
                        options.ReplayPath = arg["--replay=".Length..];
                    }
                    else
                    {
                        options.Error = $"Unknown option '{arg}'. Try --help.";
                        return options;
                    }

                    break;
            }
        }

        return options;
    }

    private static bool TryReadValue(string[] args, ref int index, out string value, CliOptions options)
    {
        value = "";
        if (index + 1 >= args.Length)
        {
            options.Error = $"Option '{args[index]}' requires a value.";
            return false;
        }

        value = args[++index];
        return true;
    }

    public static string HelpText =>
        """
        emptycli — a fake agentic coding session in your terminal.

        Usage:
          emptycli [options]

        Options:
          --speed <n>      Playback speed multiplier (default: 1, e.g. 4 or 30).
          --once           Play a single session and exit.
          --no-tui         Stream output without the alternate-screen footer.
          --no-color       Disable ANSI colors (also honours NO_COLOR).
          --replay <path>  Load a different replay.json.
          -h, --help       Show this help.
          -v, --version    Print the version.

        Controls (TUI):
          space            Pause / resume
          + / -            Increase / decrease speed
          r                Restart the current replay
          q                Quit

        The build session, project, costs and model output are simulated.
        The working directory, its folder name and the git branch are real.
        """;
}
