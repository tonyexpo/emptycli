using System.Security.Cryptography;
using EmptyCli.Replay;

namespace EmptyCli;

public sealed class SessionState
{
    private readonly ReplayPricing _pricing;

    public SessionState(ReplayMeta meta)
    {
        Meta = meta;
        _pricing = meta.Pricing ?? new ReplayPricing();
        SessionId = Convert.ToHexString(RandomNumberGenerator.GetBytes(3)).ToLowerInvariant();
    }

    public ReplayMeta Meta { get; }
    public string SessionId { get; }
    public long InputTokens { get; private set; }
    public long CachedTokens { get; private set; }
    public long OutputTokens { get; private set; }
    public long ContextTokens { get; private set; }
    public double Cost { get; private set; }
    public int Step { get; private set; }

    public bool AddUsage(ReplayEvent replayEvent)
    {
        var input = Math.Max(0, replayEvent.InputTokens);
        var cached = Math.Clamp(replayEvent.CachedTokens, 0, input);
        var output = Math.Max(0, replayEvent.OutputTokens);

        if (input == 0 && cached == 0 && output == 0)
        {
            return false;
        }

        Step++;
        InputTokens += input;
        CachedTokens += cached;
        OutputTokens += output;
        ContextTokens = input;

        var uncached = input - cached;
        Cost += uncached / 1_000_000d * _pricing.InputPerMillion;
        Cost += cached / 1_000_000d * _pricing.CachedInputPerMillion;
        Cost += output / 1_000_000d * _pricing.OutputPerMillion;

        return true;
    }

    public string FormatCost() => "$" + Cost.ToString("0.0000", System.Globalization.CultureInfo.InvariantCulture);

    public string FormatContext()
    {
        if (ContextTokens <= 0)
        {
            return "ctx 0";
        }

        return ContextTokens >= 1000
            ? $"ctx {ContextTokens / 1000d:0.#}k"
            : $"ctx {ContextTokens}";
    }

    public string FormatElapsed(TimeSpan elapsed)
    {
        var totalSeconds = (int)Math.Max(0, elapsed.TotalSeconds);
        return $"{totalSeconds / 60:00}:{totalSeconds % 60:00}";
    }
}
