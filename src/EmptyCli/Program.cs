using System.Text;
using EmptyCli;
using EmptyCli.Replay;
using EmptyCli.Rendering;

try
{
    Console.OutputEncoding = Encoding.UTF8;
}
catch
{
    // Some redirected consoles reject encoding changes; UTF-8 is still used where possible.
}

var options = CliOptions.Parse(args);

if (!string.IsNullOrWhiteSpace(options.Error))
{
    Console.Error.WriteLine("emptycli: " + options.Error);
    return 2;
}

if (options.ShowHelp)
{
    Console.WriteLine(CliOptions.HelpText);
    return 0;
}

if (options.ShowVersion)
{
    Console.WriteLine($"emptycli {CliOptions.Version} · .NET {Environment.Version}");
    return 0;
}

var replayPath = ReplayPathResolver.Resolve(options.ReplayPath);
if (replayPath is null)
{
    Console.Error.WriteLine("emptycli: could not find replay.json.");
    Console.Error.WriteLine("Looked for " + ReplayPathResolver.DescribeLookup(options.ReplayPath));
    Console.Error.WriteLine("Pass --replay <path> to point at a replay file.");
    return 1;
}

ReplayDocument document;
try
{
    document = ReplayDocument.Load(replayPath);
}
catch (Exception exception)
{
    Console.Error.WriteLine($"emptycli: failed to load '{replayPath}': {exception.Message}");
    return 1;
}

var environment = EnvironmentInfo.Capture();
var controller = new PlaybackController(options);
using var terminal = new TerminalUi(options);

Console.CancelKeyPress += (_, eventArgs) =>
{
    eventArgs.Cancel = true;
    controller.RequestQuit();
};

try
{
    terminal.Initialize(environment);
    var renderer = new ReplayRenderer(terminal, controller, environment);
    var engine = new PlaybackEngine(options, document, controller, renderer);
    return engine.Run();
}
finally
{
    controller.Dispose();
    terminal.Dispose();
}
