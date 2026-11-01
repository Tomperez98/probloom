using System.Diagnostics;
using System.Text.Json.Nodes;

namespace Probloom.Spec.Tests;

public sealed class CliRunner : IDisposable
{
    private readonly Process _process;
    private readonly StreamWriter _stdin;
    private readonly StreamReader _stdout;
    private readonly SemaphoreSlim _gate = new(1, 1);
    private readonly List<string> _stderr = new();
    private int _nextId;

    public CliRunner(string? impl = null)
    {
        var arguments = "run python -m probloom.cli";
        if (!string.IsNullOrWhiteSpace(impl))
        {
            arguments += $" --impl {impl}";
        }

        var startInfo = new ProcessStartInfo
        {
            FileName = "uv",
            Arguments = arguments,
            WorkingDirectory = TestPaths.RepoRoot,
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };

        _process = Process.Start(startInfo)
            ?? throw new InvalidOperationException("Could not start the Python CLI.");
        _stdin = _process.StandardInput;
        _stdout = _process.StandardOutput;
        _process.ErrorDataReceived += (_, args) =>
        {
            if (args.Data is not null)
            {
                lock (_stderr)
                {
                    _stderr.Add(args.Data);
                }
            }
        };
        _process.BeginErrorReadLine();
    }

    public void Reset(int capacity = 64, double errorRate = 0.01)
    {
        var response = Send(new JsonObject
        {
            ["op"] = "reset",
            ["capacity"] = capacity,
            ["error_rate"] = errorRate,
        });
        EnsureOk(response);
    }

    public bool Add(string value) => SendValue(new JsonObject { ["op"] = "add", ["value"] = value });

    public bool Contains(string value) =>
        SendValue(new JsonObject { ["op"] = "contains", ["value"] = value });

    public bool Clear() => SendValue(new JsonObject { ["op"] = "clear" });

    public JsonObject Stats()
    {
        var response = Send(new JsonObject { ["op"] = "stats" });
        EnsureOk(response);
        return response;
    }

    private bool SendValue(JsonObject body)
    {
        var response = Send(body);
        EnsureOk(response);
        return response["value"]?.GetValue<bool>() ?? true;
    }

    private JsonObject Send(JsonObject body)
    {
        _gate.Wait();
        try
        {
            body["id"] = ++_nextId;
            _stdin.WriteLine(body.ToJsonString());
            _stdin.Flush();

            var line = _stdout.ReadLine();
            if (line is null)
            {
                string stderr;
                lock (_stderr)
                {
                    stderr = string.Join(Environment.NewLine, _stderr);
                }

                throw new InvalidOperationException($"The Python CLI exited unexpectedly.{Environment.NewLine}{stderr}");
            }

            return JsonNode.Parse(line)?.AsObject()
                ?? throw new InvalidOperationException($"The Python CLI returned invalid JSON: {line}");
        }
        finally
        {
            _gate.Release();
        }
    }

    private static void EnsureOk(JsonObject response)
    {
        if (response["ok"]?.GetValue<bool>() != true)
        {
            throw new InvalidOperationException(response.ToJsonString());
        }
    }

    public void Dispose()
    {
        try
        {
            _stdin.Close();
        }
        catch
        {
            // The process may already be gone.
        }

        if (!_process.WaitForExit(1000))
        {
            _process.Kill(entireProcessTree: true);
        }

        _process.Dispose();
        _gate.Dispose();
    }
}
