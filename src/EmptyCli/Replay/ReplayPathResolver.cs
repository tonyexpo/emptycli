namespace EmptyCli.Replay;

public static class ReplayPathResolver
{
    public static string? Resolve(string? explicitPath)
    {
        var candidates = new List<string>();

        if (!string.IsNullOrWhiteSpace(explicitPath))
        {
            candidates.Add(Path.GetFullPath(explicitPath));
        }

        var current = Directory.GetCurrentDirectory();
        candidates.Add(Path.Combine(current, "replay.json"));

        var dir = new DirectoryInfo(current);
        for (var depth = 0; depth < 5 && dir is not null; depth++)
        {
            candidates.Add(Path.Combine(dir.FullName, "replay.json"));
            dir = dir.Parent;
        }

        candidates.Add(Path.Combine(AppContext.BaseDirectory, "replay.json"));

        return candidates
            .Select(Path.GetFullPath)
            .Distinct(StringComparer.Ordinal)
            .FirstOrDefault(File.Exists);
    }

    public static string DescribeLookup(string? explicitPath)
    {
        if (!string.IsNullOrWhiteSpace(explicitPath))
        {
            return $"'{Path.GetFullPath(explicitPath)}'";
        }

        return $"'{Path.Combine(Directory.GetCurrentDirectory(), "replay.json")}' or next to the executable";
    }
}
