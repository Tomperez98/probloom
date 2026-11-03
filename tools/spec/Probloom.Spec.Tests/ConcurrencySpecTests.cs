using System.Diagnostics;
using System.Text.Json;
using Microsoft.Accordant;
using Xunit;

namespace Probloom.Spec.Tests;

public sealed class ConcurrencySpecTests
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
    };

    private static InputSet Inputs(ProbloomSpec spec)
    {
        var add = spec.GetOperation<string, bool>("Add");
        var contains = spec.GetOperation<string, bool>("Contains");
        var clear = spec.GetOperation<bool, bool>("Clear");

        return new InputSet
        {
            add.With("alice", "Add alice"),
            add.With("bob", "Add bob"),
            add.With("ghost", "Add ghost"),
            contains.With("alice", "Contains alice"),
            contains.With("bob", "Contains bob"),
            contains.With("ghost", "Contains ghost"),
            clear.With(true, "Clear"),
        };
    }

    private static ConcurrentTestCase WithPostGroupReads(ConcurrentTestCase test, InputSet inputs)
    {
        test.Segments.Add(new TestCaseSegment(
            new OperationCall("Contains alice (after)", inputs["Contains alice"])));
        test.Segments.Add(new TestCaseSegment(
            new OperationCall("Contains bob (after)", inputs["Contains bob"])));
        test.Segments.Add(new TestCaseSegment(
            new OperationCall("Contains ghost (after)", inputs["Contains ghost"])));
        test.Description = TestCaseGenerator.ConstructDescriptionForConcurrentTestCase(test.Segments);
        return test;
    }

    private static IList<ConcurrentTestCase> BuildCases(
        ProbloomSpec spec,
        InputSet inputs,
        TestingContext context)
    {
        var generator = ConcurrentTestCaseAlgorithms.CreateDefaultConcurrentTestCaseGenerator(
            maxConcurrencyLevel: 3);

        var options = new TestGenerationOptions
        {
            MaxDepth = 4,
            MaxOperationApplicationCount = 2,
            StateConstraint = _ => true,
            ConcurrentTestCaseAlgorithm = (ctx, root) =>
                generator(ctx, root).Select(test => WithPostGroupReads(test, inputs)).ToList(),
        };

        var cases = spec.GenerateConcurrentTests(new FilterState(), inputs, options).ToList();

        var addWins = TestCaseGenerator.CreateManualConcurrentTestCase(
            context,
            inputs,
            sequentialPrefixOperationNames: Array.Empty<string>(),
            concurrentOperationNames: new[] { "Add alice", "Add bob" });
        cases.Add(WithPostGroupReads(addWins, inputs));

        var clearWins = TestCaseGenerator.CreateManualConcurrentTestCase(
            context,
            inputs,
            sequentialPrefixOperationNames: Array.Empty<string>(),
            concurrentOperationNames: new[] { "Add alice", "Clear" });
        cases.Add(WithPostGroupReads(clearWins, inputs));

        return cases;
    }

    private static void RunPythonExecutor(string casesPath, string tracesPath)
    {
        var startInfo = new ProcessStartInfo
        {
            FileName = "uv",
            Arguments = $"run python tools/harness/concurrency.py \"{casesPath}\" \"{tracesPath}\"",
            WorkingDirectory = TestPaths.RepoRoot,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };

        using var process = Process.Start(startInfo)
            ?? throw new InvalidOperationException("Could not start the concurrency executor.");
        var stdout = process.StandardOutput.ReadToEnd();
        var stderr = process.StandardError.ReadToEnd();
        process.WaitForExit();

        Assert.True(
            process.ExitCode == 0,
            $"Concurrency executor failed ({process.ExitCode}):{Environment.NewLine}{stdout}{Environment.NewLine}{stderr}");
    }

    private static void Replay(ProbloomSpec spec, TraceCase trace)
    {
        var profile = new StateProfile(new FilterState());

        foreach (var segment in trace.Segments)
        {
            if (segment.Count == 1)
            {
                var call = segment[0];
                var operation = spec.GetOperation(call.Operation);
                var request = JsonSerializer.Deserialize(
                    call.Request.GetRawText(), operation.RequestType)!;
                var response = JsonSerializer.Deserialize(
                    call.Response.GetRawText(), operation.ResponseType)!;

                var (ok, message, next) = spec.Allows(operation, request, response, profile);
                Assert.True(ok, $"{trace.Description}: {message}");
                profile = next;
            }
            else
            {
                var calls = segment.Select(call =>
                {
                    var operation = spec.GetOperation(call.Operation);
                    var request = JsonSerializer.Deserialize(
                        call.Request.GetRawText(), operation.RequestType)!;
                    var response = JsonSerializer.Deserialize(
                        call.Response.GetRawText(), operation.ResponseType)!;
                    return ((IOperation)operation, request, response);
                }).ToList();

                var (ok, message, next) = spec.AllowsConcurrent(profile, calls);
                Assert.True(ok, $"{trace.Description}: {message}");
                profile = next;
            }
        }
    }

    [Fact]
    public void Generated_and_pinned_cases_are_linearizable()
    {
        var spec = new ProbloomSpec();
        var inputs = Inputs(spec);
        var context = spec.CreateTestingContext("probloom");
        var cases = BuildCases(spec, inputs, context);
        Assert.NotEmpty(cases);

        var directory = Path.Combine(
            Path.GetTempPath(),
            "probloom-concurrency-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(directory);

        try
        {
            var casesPath = Path.Combine(directory, "cases.json");
            var tracesPath = Path.Combine(directory, "traces.json");
            File.WriteAllText(
                casesPath,
                TestCaseGenerator.SerializeConcurrentTestCases(context, cases));

            RunPythonExecutor(casesPath, tracesPath);

            var traces = JsonSerializer.Deserialize<TraceFile>(
                File.ReadAllText(tracesPath), JsonOptions)!;
            Assert.Equal(cases.Count, traces.Cases.Count);
            Assert.All(
                traces.Cases,
                trace => Assert.Contains(trace.Segments, segment => segment.Count > 1));
            foreach (var trace in traces.Cases)
            {
                Replay(spec, trace);
            }
        }
        finally
        {
            Directory.Delete(directory, recursive: true);
        }
    }
}
