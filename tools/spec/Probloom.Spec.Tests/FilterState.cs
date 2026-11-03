using Microsoft.Accordant;

namespace Probloom.Spec.Tests;

[State]
public partial class FilterState
{
    public Dictionary<string, bool> Inserted { get; set; } = new();
}
