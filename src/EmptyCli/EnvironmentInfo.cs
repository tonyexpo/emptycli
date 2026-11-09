namespace EmptyCli;

public sealed record EnvironmentInfo(
    string CurrentDirectory,
    string HomeDirectory,
    string FolderName,
    string Branch,
    string Version)
{
    public static EnvironmentInfo Capture()
    {
        var current = Directory.GetCurrentDirectory();
        var home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        var folder = new DirectoryInfo(current).Name;
        if (string.IsNullOrWhiteSpace(folder))
        {
            folder = current.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        }

        return new EnvironmentInfo(current, home, folder, GitBranchReader.Find(current), CliOptions.Version);
    }

    public string ShortPath
    {
        get
        {
            if (string.IsNullOrEmpty(HomeDirectory))
            {
                return CurrentDirectory;
            }

            if (CurrentDirectory.Equals(HomeDirectory, StringComparison.Ordinal))
            {
                return "~";
            }

            var withSeparator = HomeDirectory.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
            if (CurrentDirectory.StartsWith(withSeparator, StringComparison.Ordinal))
            {
                return "~" + CurrentDirectory[HomeDirectory.Length..];
            }

            return CurrentDirectory;
        }
    }
}

internal static class GitBranchReader
{
    public static string Find(string startDirectory)
    {
        try
        {
            var directory = new DirectoryInfo(startDirectory);
            while (directory is not null)
            {
                var gitPath = Path.Combine(directory.FullName, ".git");
                if (Directory.Exists(gitPath))
                {
                    return ReadHead(Path.Combine(gitPath, "HEAD"));
                }

                if (File.Exists(gitPath))
                {
                    // Worktrees store a "gitdir: <path>" pointer in .git.
                    var pointer = File.ReadAllText(gitPath).Trim();
                    if (pointer.StartsWith("gitdir:", StringComparison.OrdinalIgnoreCase))
                    {
                        var target = pointer["gitdir:".Length..].Trim();
                        if (!Path.IsPathRooted(target))
                        {
                            target = Path.GetFullPath(Path.Combine(directory.FullName, target));
                        }

                        return ReadHead(Path.Combine(target, "HEAD"));
                    }
                }

                directory = directory.Parent;
            }
        }
        catch
        {
            // A missing or malformed repository should never break playback.
        }

        return "no-vcs";
    }

    private static string ReadHead(string headPath)
    {
        try
        {
            if (!File.Exists(headPath))
            {
                return "no-vcs";
            }

            var head = File.ReadAllText(headPath).Trim();
            const string prefix = "ref: refs/heads/";
            if (head.StartsWith(prefix, StringComparison.Ordinal))
            {
                return head[prefix.Length..];
            }

            return head.Length >= 7 ? head[..7] : head;
        }
        catch
        {
            return "no-vcs";
        }
    }
}
