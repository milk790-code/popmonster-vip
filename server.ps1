$http = [System.Net.HttpListener]::new()
$http.Prefixes.Add("http://localhost:8000/")
$http.Start()
Write-Host "Server started on http://localhost:8000/"
while ($http.IsListening) {
    $context = $http.GetContext()
    $requestUrl = $context.Request.Url
    $localPath = $requestUrl.LocalPath
    $filePath = Join-Path (Get-Location) $localPath
    if ($localPath -eq "/") { $filePath = Join-Path $filePath "index.html" }
    if (Test-Path $filePath) {
        $content = Get-Content $filePath -Raw
        $response = $context.Response
        $response.ContentType = "text/html; charset=utf-8"
        $response.ContentLength64 = [System.Text.Encoding]::UTF8.GetByteCount($content)
        $response.OutputStream.Write([System.Text.Encoding]::UTF8.GetBytes($content), 0, [System.Text.Encoding]::UTF8.GetByteCount($content))
        $response.OutputStream.Close()
    } else {
        $context.Response.StatusCode = 404
        $context.Response.OutputStream.Close()
    }
}