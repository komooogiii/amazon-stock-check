$url = "https://www.amazon.co.jp/baby-reg/welcomebox?_encoding=UTF8&ref_=cct_cg_PXbenefit_2b1&pf_rd_p=9cc85c64-a328-41c8-b7be-e1dcaa476709&pf_rd_r=VHCS878C8VFC2T3FVY43"
$stateFile = "amazon_stock_state.txt"
$logFile = "amazon_stock_check.log"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

# Discord Webhook URL from environment variable
$discordWebhookUrl = $env:DISCORD_WEBHOOK

try {
    Add-Content $logFile "$timestamp - Check started"

    $response = Invoke-WebRequest -Uri $url -UserAgent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" -TimeoutSec 10 -Headers @{"Accept-Language"="ja-JP,ja;q=0.9"}
    $html = $response.Content

    $isInStock = $html -match "in stock|available|order now" -or $html -notmatch "out of stock|sold out"

    $previousState = if (Test-Path $stateFile) { Get-Content $stateFile } else { "out_of_stock" }
    $currentState = if ($isInStock) { "in_stock" } else { "out_of_stock" }

    Add-Content $logFile "$timestamp - Previous: $previousState, Current: $currentState"

    if ($currentState -eq "in_stock" -and $previousState -eq "out_of_stock") {
        Add-Content $logFile "$timestamp - Stock detected!"

        # Discord notification
        if ($discordWebhookUrl) {
            try {
                $discordPayload = @{
                    content = "🎉 **Amazon Baby Welcome Box is IN STOCK!**`n$url"
                } | ConvertTo-Json

                Invoke-WebRequest -Uri $discordWebhookUrl -Method Post -Body $discordPayload -ContentType "application/json" -TimeoutSec 10
                Add-Content $logFile "$timestamp - Discord notification sent"
            }
            catch {
                Add-Content $logFile "$timestamp - Discord error: $_"
            }
        }
    }

    Set-Content $stateFile $currentState
    Add-Content $logFile "$timestamp - Check completed"
}
catch {
    Add-Content $logFile "$timestamp - Error: $_"
}
