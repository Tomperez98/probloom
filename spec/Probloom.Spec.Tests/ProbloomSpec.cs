using Microsoft.Accordant;

namespace Probloom.Spec.Tests;

public sealed class ProbloomSpec : Spec<FilterState>
{
    public ProbloomSpec()
    {
        WithJsonPrinters();

        Operation<string, bool>("Add", (element, _) =>
            Expect.That<bool>(r => r, $"Insert '{element}' → accepted")
                  .ThenState<FilterState>(next =>
                  {
                      next.Inserted[element] = true;
                      Invariant.Assert(
                          next.Inserted.ContainsKey(element),
                          "Add must record the element");
                  }));

        Operation<string, bool>("Contains", (element, state) =>
        {
            if (state.Inserted.ContainsKey(element))
            {
                return Expect.That<bool>(
                        r => r,
                        $"'{element}' was inserted → contains must be true")
                    .SameState();
            }

            if (state.Inserted.Count == 0)
            {
                return Expect.That<bool>(
                        r => !r,
                        $"filter is empty → contains('{element}') must be false")
                    .SameState();
            }

            return Expect.That<bool>(
                    r => true,
                    $"'{element}' was never inserted and the filter is not empty → contains may be true or false")
                .SameState();
        });

        Operation<bool, bool>("Clear", (_, _) =>
            Expect.That<bool>(
                    r => r,
                    "Clear → accepted; every membership query now returns false")
                .ThenState<FilterState>(next =>
                {
                    next.Inserted.Clear();
                    Invariant.Assert(
                        next.Inserted.Count == 0,
                        "Clear must empty the abstract set");
                }));
    }
}
