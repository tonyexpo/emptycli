using EmptyCli.Replay;
using EmptyCli.Rendering;

namespace EmptyCli;

public sealed class PlaybackEngine
{
    private readonly CliOptions _options;
    private readonly ReplayDocument _document;
    private readonly PlaybackController _controller;
    private readonly ReplayRenderer _renderer;

    public PlaybackEngine(
        CliOptions options,
        ReplayDocument document,
        PlaybackController controller,
        ReplayRenderer renderer)
    {
        _options = options;
        _document = document;
        _controller = controller;
        _renderer = renderer;
    }

    public int Run()
    {
        _controller.Start();
        var loop = 0;

        while (!_controller.QuitRequested)
        {
            loop++;
            _controller.ResetRestart();
            var state = new SessionState(_document.Meta);
            _renderer.BeginSession(state, loop);

            foreach (var replayEvent in _document.Events)
            {
                if (_controller.QuitRequested || _controller.RestartRequested)
                {
                    break;
                }

                _controller.Delay(replayEvent.Gap, _renderer.Tick);
                if (_controller.QuitRequested || _controller.RestartRequested)
                {
                    break;
                }

                if (state.AddUsage(replayEvent))
                {
                    _renderer.Tick(force: true);
                }

                _renderer.Render(replayEvent, state);
                _renderer.Tick();
            }

            if (_controller.QuitRequested)
            {
                break;
            }

            var restarted = _controller.RestartRequested;
            if (!restarted)
            {
                _renderer.EndSession(state, _options.Once);
            }

            if (_options.Once)
            {
                break;
            }

            _controller.ResetRestart();
            for (var tick = 0; tick < 24 && !_controller.QuitRequested; tick++)
            {
                if (_controller.RestartRequested)
                {
                    break;
                }

                _controller.DelayMs(restarted ? 25 : 250, _renderer.Tick);
            }

            _controller.ResetRestart();
        }

        return 0;
    }
}
