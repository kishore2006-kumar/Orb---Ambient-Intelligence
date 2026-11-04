## ------------------- Running -------------------

🪟 Window A: Mosquitto Broker

Open your first PowerShell window (Run as Administrator) to stop the background conflict service and run the broker manually:

```powershell
Stop-Service -Name "mosquitto" -ErrorAction SilentlyContinue
cd "C:\Program Files\Mosquitto"
.\mosquitto.exe -c C:\mosquitto\orb.conf -v
```

Use code with caution.
Leave this window completely open. Do not type anything else here.

🪟 Window B: The Hub (FastAPI Backend)

Open a second PowerShell window, navigate to your project root folder, and start the Uvicorn server:

```powershell
cd K:\ORB-Project\
.\.venv\Scripts\Activate.ps1
uvicorn hub.main:create_app --reload
```

Use code with caution.
Leave this window completely open to monitor API stream logging outputs.

🪟 Window C: The Laptop Agent

Open a third PowerShell window to run your actual background laptop daemon loops
Leave this window as it is.

🪟 Window D: The Test Space

Open a fourth PowerShell window.

```powershell
   Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/devices/pair/start -Headers @{ "X-Hub-Token" = "<your HUB_API_TOKEN>" } -ContentType "application/json" -Body '{"device_type":"laptop","os":"windows"}'
   ```
This will generate a code -> <CODE_FROM_HUB>
*** Caution : Use this code in the Window C immediately, along with the powershell script ***

🪟 Window C: The Laptop Agent

Then switch to Window C

```powershell
    .\.venv\Scripts\Activate.ps1

    python -m agent_windows.main pair --code <CODE_FROM_HUB>

    python -m agent_windows.main run
```

Use code with caution.
Leave this window open. It should display a line reading 

```
INFO:__main__:MQTT connected: Success.
```

🪟 Window D: The Test Space

Switch to Window D 

Run the testing steps one by one to monitor and control your system.

*** Refer to README.md for more information or use Interactive Page to run the testing steps ***

## ------------------- TESTING -------------------

## Step 1: Put your token into the window

Find your token first. Open `K:\ORB-Project\.env` in Notepad, find the line `HUB_API_TOKEN=...`, and copy everything **after** the `=`. Don't paste the token into this chat.

Paste this into window D, replacing `<your token>` including the angle brackets, but keeping the quote marks:

```powershell
$token = "<your token>"
$base  = "http://127.0.0.1:8000"
$h     = @{ "X-Hub-Token" = $token }
```

Nothing prints. That's normal.

Then paste this helper, and press Enter twice if the cursor waits:

```powershell
function Send-Cmd($id, $action, $params = '{}') {
  $body = '{"device_id":"' + $id + '","action":"' + $action + '","params":' + $params + ',"source":"api"}'
  try {
    Invoke-RestMethod -Method Post -Uri "$base/commands" -Headers $h -ContentType "application/json" -Body $body |
      Select-Object action, status, risk, error
  } catch { $_.ErrorDetails.Message }
}
```

These settings live **only in this window**. If you close it, repeat Step 1.

## Step 2: Health and security

```powershell
Invoke-RestMethod "$base/health"
try { Invoke-RestMethod "$base/devices" } catch { $_.Exception.Response.StatusCode.value__ }
```

**You should see:** `status ok`, `version 0.1.0`, then `401`. The 401 shows the hub refuses requests with no token.

## Step 3: Create a virtual device and test all actions

```powershell
$v = Invoke-RestMethod -Method Post -Uri "$base/devices/virtual" -Headers $h -ContentType "application/json" -Body '{"name":"Manual Tablet","type":"tablet","os":"android"}'
$v | Select-Object id, name, type, driver
foreach ($a in "status","wake","mute","unmute","volume_up","volume_down","lock","sleep") { Send-Cmd $v.id $a }
Send-Cmd $v.id "launch_app" '{"app":"notepad"}'
```

**You should see:** a device row, then nine result rows with `status = acked`. `lock`, `sleep` and `launch_app` show `risk = medium`, and the rest show `safe`.

## Step 4: Things that must be rejected

```powershell
Send-Cmd $v.id "unlock"
Send-Cmd $v.id "volume"
Send-Cmd $v.id "launch_app"
Send-Cmd $v.id "volume_up" '{"x":1}'
Send-Cmd "no-such-id" "status"
```

**You should see** these codes, in order: `unknown_action`, `unknown_action`, `invalid_params`, `invalid_params`, `device_not_found`. The first line proves the system has no unlock command.

## Step 5: The bulk safety rule

```powershell
$b1 = '{"device_ids":["' + $v.id + '"],"action":"lock","params":{},"source":"api"}'
try { Invoke-RestMethod -Method Post -Uri "$base/commands/bulk" -Headers $h -ContentType "application/json" -Body $b1 } catch { $_.ErrorDetails.Message }
$b2 = '{"device_ids":["' + $v.id + '"],"action":"lock","params":{},"source":"api","confirm":true}'
Invoke-RestMethod -Method Post -Uri "$base/commands/bulk" -Headers $h -ContentType "application/json" -Body $b2 | ConvertTo-Json -Depth 5
```

**You should see:** first an error with `confirmation_required`, then a result block once `confirm` is `true`.

## Step 6: History

```powershell
Invoke-RestMethod "$base/commands?limit=5" -Headers $h | Select-Object action, status, created_at
```

**You should see:** at most 5 rows, newest first.

## Step 7: Live WebSocket (this one is in the browser, window E)

1. In your browser, open `http://127.0.0.1:8000/docs` and press **F12**.
2. Click the **Console** tab. If Chrome says "don't paste code", type `allow pasting` and press Enter.
3. Paste this, replacing `<your token>`, and press Enter: `ws = new WebSocket("ws://127.0.0.1:8000/ws/ui?token=<your token>"); ws.onmessage = e => console.log(e.data)`
4. Go back to window D and run `Send-Cmd $v.id "status"`.
5. **You should see** a `command_update` message appear in the browser console immediately.

## Step 8: Your real laptop

1. Start Mosquitto (window A) and the hub (window B). If the agent isn't paired yet, follow README step 5.
2. In a new window C, run from `K:\ORB-Project\`:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   python -m agent_windows.main run
   ```

   Leave it open.
3. In window D, find the laptop:

   ```powershell
   $devs = Invoke-RestMethod "$base/devices" -Headers $h
   $devs | Select-Object id, name, driver, status, battery
   $lap = @($devs | Where-Object { $_.driver -eq "windows_agent" })[0]
   ```

   The laptop should say `online` within 30 seconds.
4. Run these **one at a time**, and watch your laptop after each:

   ```powershell
   Send-Cmd $lap.id "status"
   Send-Cmd $lap.id "volume_up"
   Send-Cmd $lap.id "volume_down"
   Send-Cmd $lap.id "mute"
   Send-Cmd $lap.id "unmute"
   Send-Cmd $lap.id "launch_app" '{"app":"notepad"}'
   Send-Cmd $lap.id "launch_app" '{"app":"evil"}'
   ```

   **You should see:** each row `acked`, except `evil`, which fails with `app_not_allowed`. Volume moves about 10 points each time, and Notepad opens.

5. Last, run `Send-Cmd $lap.id "lock"` and then `Send-Cmd $lap.id "sleep"`. These lock and sleep the laptop that is also running the hub, so save your work first. You unlock it yourself.

## Step 9: Clean up

```powershell
Invoke-RestMethod -Method Delete -Uri "$base/devices/$($v.id)" -Headers $h
```

## If something goes wrong

| What you see | Meaning | Fix |
|---|---|---|
| `Unable to connect to the remote server` | The hub isn't running | Start it in window B |
| `The term 'Send-Cmd' is not recognized` | Step 1 wasn't run in this window | Paste Step 1 again |
| `401` on every call | Wrong or empty token | Redo the `$token` line without the `< >` |
| The laptop stays `unknown`, or commands say `timeout` | The agent isn't running or can't reach the broker | Check windows A and C |
| `device_offline` | The agent stopped | Restart window C |

## Also Check README.md, DEVICE_CHECKLIST.md and MOSQUITTO.md for more info about the processes


## THESE ARE THE FEW IMPORTANT COMMANDS FOR TESTING USING THE INTERACTIVE PAGE

| action | params |risk | 
|--------|--------|-----|
| status | {} | safe|
| volume_up | {} | safe|
| volume_down | {} | safe|
| mute | {} | safe|
| unmute | {} | safe|
| lock | {} | medium|
| sleep | {} | medium|
| launch_app | {"app":"notepad"} | medium|
| launch_app | {"app":"evil"} | high|

## FOR LAUNCH APP THERE ARE A FEW MORE COMMANDS

Here are the most common short execution names you can drop straight into your Send-Cmd line:

• Google Chrome: "chrome"
• Microsoft Edge: "msedge"
• Paint: "mspaint"
• Snipping Tool: "snippingtool"
• WordPad: "write"
• Command Prompt: "cmd"
• Control Panel: "control"
• Windows Settings: "start ms-settings:"

## TO USE 

```powershell
    Send-Cmd $lap.id "launch_app" '{"app":"YOUR_APP"}'
```

## TO KILL

```powershell
    Send-Cmd $lap.id "kill_app" '{"app":"YOUR_APP"}'
```

## TURN OFF THE LAPTOP

```powershell
    Send-Cmd $lap.id "shutdown"
```
