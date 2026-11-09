using System.Diagnostics;

namespace EmptyCli;

/// <summary>
/// Owns the session clock, pause state, playback speed and keyboard shortcut loop.
/// </summary>
public sealed class PlaybackController : IDisposable
{
    private readonly Stopwatch _clock = new();
    private readonly object _gate = new();
    private Thread? _keyboardThread;
    private volatile bool _paused;
    private volatile bool _quit;
    private volatile bool _restart;
    private double _speed;

    public PlaybackController(CliOptions options)
    {
        _speed = options.Speed;
        ListenForKeys = !options.NoTui && !Console.IsInputRedirected && !Console.IsOutputRedirected;
    }

    public bool ListenForKeys { get; }
    public bool Paused => _paused;
    public bool QuitRequested => _quit;
    public bool RestartRequested => _restart;
    public double Speed => _speed;
    public TimeSpan Elapsed => _clock.Elapsed;

    public void Start()
    {
        _clock.Start();

        if (ListenForKeys)
        {
            _keyboardThread = new Thread(KeyboardLoop)
            {
                IsBackground = true,
                Name = "emptycli-keyboard",
            };
            _keyboardThread.Start();
        }
    }

    public void Delay(double seconds, Action? tick = null)
    {
        DelayMs(seconds * 1000d, tick);
    }

    public void DelayMs(double milliseconds, Action? tick = null)
    {
        if (milliseconds <= 0 || _quit)
        {
            tick?.Invoke();
            return;
        }

        var scaled = milliseconds / Math.Max(0.05, _speed);
        if (scaled < 1.0)
        {
            tick?.Invoke();
            return;
        }

        var start = _clock.Elapsed;

        while (!_quit)
        {
            tick?.Invoke();

            if (_paused)
            {
                Thread.Sleep(40);
                continue;
            }

            var elapsed = (_clock.Elapsed - start).TotalMilliseconds;
            if (elapsed >= scaled)
            {
                break;
            }

            var remaining = scaled - elapsed;
            Thread.Sleep((int)Math.Clamp(remaining, 1, 30));
        }
    }

    public void TogglePause()
    {
        lock (_gate)
        {
            _paused = !_paused;
            if (_paused)
            {
                _clock.Stop();
            }
            else
            {
                _clock.Start();
            }
        }
    }

    public void ChangeSpeed(double factor)
    {
        lock (_gate)
        {
            _speed = Math.Clamp(_speed * factor, 0.25, 64);
        }
    }

    public void RequestQuit() => _quit = true;

    public void RequestRestart() => _restart = true;

    public void ResetRestart() => _restart = false;

    public void Dispose()
    {
        _quit = true;
        _clock.Stop();
    }

    private void KeyboardLoop()
    {
        try
        {
            while (!_quit)
            {
                if (!Console.KeyAvailable)
                {
                    Thread.Sleep(40);
                    continue;
                }

                var key = Console.ReadKey(intercept: true);
                switch (key.Key)
                {
                    case ConsoleKey.Spacebar:
                        TogglePause();
                        break;
                    case ConsoleKey.Q:
                        RequestQuit();
                        break;
                    case ConsoleKey.R:
                        RequestRestart();
                        break;
                    case ConsoleKey.OemPlus:
                    case ConsoleKey.Add:
                        ChangeSpeed(2);
                        break;
                    case ConsoleKey.OemMinus:
                    case ConsoleKey.Subtract:
                        ChangeSpeed(0.5);
                        break;
                    case ConsoleKey.Escape:
                        RequestQuit();
                        break;
                }
            }
        }
        catch
        {
            // Input can disappear when a terminal is detached; playback keeps running.
        }
    }
}
