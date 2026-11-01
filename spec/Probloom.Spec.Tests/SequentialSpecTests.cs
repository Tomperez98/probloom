using Microsoft.Accordant;
using Xunit;

namespace Probloom.Spec.Tests;

public sealed class SequentialSpecTests
{
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

    private static TestGenerationOptions Generation() => new()
    {
        MaxDepth = -1,
        MaxOperationApplicationCount = 4,
        StateConstraint = _ => true,
        SequentialTestCaseAlgorithm = SequentialTestCaseAlgorithms.StateCoverage,
    };

    private static async Task<IList<TestCaseExecutionResult>> RunSuite(string? impl = null)
    {
        var spec = new ProbloomSpec();
        var inputs = Inputs(spec);
        using var cli = new CliRunner(impl);
        var context = spec.CreateTestingContext("probloom");
        context.Register(cli);

        spec.ExecuteWith<CliRunner>()
            .Bind<string, bool>("Add", (runner, element) => runner.Add(element))
            .Bind<string, bool>("Contains", (runner, element) => runner.Contains(element))
            .Bind<bool, bool>("Clear", (runner, _) => runner.Clear())
            .Done();

        var options = new TestExecutionOptions
        {
            StopOnFirstFailure = false,
            BeforeEach = info => info.Context.Get<CliRunner>().Reset(),
        };

        var initial = new FilterState();
        var tests = spec.GenerateTests(initial, inputs, Generation()).ToList();
        tests.Add(TestCaseGenerator.CreateManualSequentialTestCase(
            context,
            inputs,
            "Add alice",
            "Clear",
            "Contains alice"));

        return await spec.RunTests(context, initial, tests, options);
    }

    [Fact]
    public async Task Generated_suite_is_green()
    {
        var results = await RunSuite();

        Assert.True(results.All(result => result.Success), FirstFailure(results));
    }

    [Fact]
    public async Task Faulty_add_is_rejected()
    {
        var results = await RunSuite("bugs.faulty_add");

        Assert.Contains(results, result => !result.Success && HasMessage(
            result, "was inserted → contains must be true"));
    }

    [Fact]
    public async Task Faulty_clear_is_rejected()
    {
        var results = await RunSuite("bugs.faulty_clear");

        Assert.Contains(results, result => !result.Success && HasMessage(
            result, "filter is empty → contains('alice') must be false"));
    }

    [Fact]
    public async Task Faulty_contains_is_rejected()
    {
        var results = await RunSuite("bugs.faulty_contains");

        Assert.Contains(results, result => !result.Success && HasMessage(
            result, "was inserted → contains must be true"));
    }

    [Fact]
    public async Task Always_true_passes_the_spec()
    {
        var results = await RunSuite("bugs.always_true");

        Assert.All(results, result => Assert.True(result.Success, result.LastFailureMessage));
    }

    private static string FirstFailure(IEnumerable<TestCaseExecutionResult> results) =>
        results.FirstOrDefault(result => !result.Success)?.LastFailureMessage ?? "no failure";

    private static bool HasMessage(TestCaseExecutionResult result, string expected) =>
        result.LastFailureMessage?.Contains(expected, StringComparison.Ordinal) == true;
}
