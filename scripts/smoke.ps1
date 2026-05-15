param(
    [string]$BaseUrl = "http://localhost:8080",
    [string]$ApiKey = ""
)

$headers = @{}
if ($ApiKey -ne "") {
    $headers["Authorization"] = "Bearer $ApiKey"
}

Invoke-RestMethod -Method Get -Uri "$BaseUrl/v1/health"
Invoke-RestMethod -Method Post -Uri "$BaseUrl/v1/ingest/events" -ContentType "application/json" -Headers $headers -InFile "examples/worked-example.json"
Invoke-RestMethod -Method Post -Uri "$BaseUrl/v1/context/reconstruct" -ContentType "application/json" -Headers $headers -InFile "examples/reconstruct-request.json"
