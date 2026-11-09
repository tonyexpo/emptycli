using System.Text.Json;
using System.Text.Json.Serialization;

namespace EmptyCli.Replay;

public sealed class ReplayDocument
{
    [JsonPropertyName("version")]
    public int Version { get; set; } = 1;

    [JsonPropertyName("meta")]
    public ReplayMeta Meta { get; set; } = new();

    [JsonPropertyName("events")]
    public List<ReplayEvent> Events { get; set; } = [];

    public static ReplayDocument Load(string path)
    {
        var json = File.ReadAllText(path);
        var document = JsonSerializer.Deserialize<ReplayDocument>(json, JsonOptions)
            ?? throw new InvalidDataException("replay.json is empty or invalid.");

        if (document.Events is null || document.Events.Count == 0)
        {
            throw new InvalidDataException("replay.json does not contain any events.");
        }

        document.Meta ??= new ReplayMeta();
        return document;
    }

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        AllowTrailingCommas = true,
        ReadCommentHandling = JsonCommentHandling.Skip,
    };
}

public sealed class ReplayMeta
{
    [JsonPropertyName("title")]
    public string Title { get; set; } = "An emptycli session";

    [JsonPropertyName("project")]
    public string Project { get; set; } = "emptycli";

    [JsonPropertyName("description")]
    public string Description { get; set; } = "";

    [JsonPropertyName("model")]
    public string Model { get; set; } = "openrouter/deepseek-v4.1-flash-1017";

    [JsonPropertyName("modelName")]
    public string ModelName { get; set; } = "DeepSeek V4.1 Flash 1017";

    [JsonPropertyName("provider")]
    public string Provider { get; set; } = "openrouter";

    [JsonPropertyName("totalSeconds")]
    public double TotalSeconds { get; set; }

    [JsonPropertyName("pricing")]
    public ReplayPricing Pricing { get; set; } = new();

    [JsonPropertyName("outro")]
    public string? Outro { get; set; }

    [JsonPropertyName("outroUrl")]
    public string? OutroUrl { get; set; }
}

public sealed class ReplayPricing
{
    [JsonPropertyName("inputPerM")]
    public double InputPerMillion { get; set; } = 0.28;

    [JsonPropertyName("cachedInputPerM")]
    public double CachedInputPerMillion { get; set; } = 0.07;

    [JsonPropertyName("outputPerM")]
    public double OutputPerMillion { get; set; } = 1.10;
}

public sealed class ReplayEvent
{
    [JsonPropertyName("kind")]
    public string Kind { get; set; } = "";

    [JsonPropertyName("gap")]
    public double Gap { get; set; }

    [JsonPropertyName("ms")]
    public double Ms { get; set; }

    [JsonPropertyName("text")]
    public string? Text { get; set; }

    [JsonPropertyName("style")]
    public string? Style { get; set; }

    [JsonPropertyName("tool")]
    public string? Tool { get; set; }

    [JsonPropertyName("arg")]
    public string? Arg { get; set; }

    [JsonPropertyName("detail")]
    public string? Detail { get; set; }

    [JsonPropertyName("status")]
    public string? Status { get; set; }

    [JsonPropertyName("add")]
    public int Additions { get; set; }

    [JsonPropertyName("del")]
    public int Deletions { get; set; }

    [JsonPropertyName("in")]
    public int InputTokens { get; set; }

    [JsonPropertyName("cache")]
    public int CachedTokens { get; set; }

    [JsonPropertyName("out")]
    public int OutputTokens { get; set; }

    [JsonPropertyName("todos")]
    public List<ReplayTodo>? Todos { get; set; }
}

public sealed class ReplayTodo
{
    [JsonPropertyName("text")]
    public string Text { get; set; } = "";

    [JsonPropertyName("status")]
    public string Status { get; set; } = "pending";
}
