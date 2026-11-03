using System.Text.Json;
using System.Text.Json.Serialization;

namespace Probloom.Spec.Tests;

public sealed class TraceFile
{
    [JsonPropertyName("cases")]
    public List<TraceCase> Cases { get; set; } = new();
}

public sealed class TraceCase
{
    [JsonPropertyName("description")]
    public string? Description { get; set; }

    [JsonPropertyName("segments")]
    public List<List<TraceCall>> Segments { get; set; } = new();
}

public sealed class TraceCall
{
    [JsonPropertyName("operation")]
    public string Operation { get; set; } = string.Empty;

    [JsonPropertyName("request")]
    public JsonElement Request { get; set; }

    [JsonPropertyName("response")]
    public JsonElement Response { get; set; }
}
