# Mosquitto setup (Windows)

These steps match Mosquitto 2.x. Check the official Mosquitto documentation for your installed version.
Default install folder: `C:\Program Files\mosquitto`. Create the folder `C:\mosquitto` first for your own files.

## 1. Create users (run from `C:\Program Files\mosquitto\`)

```powershell
.\mosquitto_passwd.exe -c C:\mosquitto\passwd.txt orb_hub
.\mosquitto_passwd.exe C:\mosquitto\passwd.txt orb_agent
```

Each command prompts for a password (the `-c` flag creates the file, so use it only for the first user).
Use the `orb_hub` password as `MQTT_PASSWORD` in `.env`, and the `orb_agent` password as `mqtt_password` in `agent_windows/config.json`.

## 2. Create `C:\mosquitto\orb.conf`

```
listener 1883 127.0.0.1
allow_anonymous false
password_file C:\mosquitto\passwd.txt
```

`127.0.0.1` accepts local connections only. To let agents on other machines connect, change it to the hub's LAN address and allow port 1883 in the Windows firewall for the private network only.

## 3. Run the broker (from `C:\Program Files\mosquitto\`)

```powershell
.\mosquitto.exe -c C:\mosquitto\orb.conf -v
```

Leave the window open while the hub and agent run.

## Troubleshooting: "Not authorized" or "not authorised"

This means the broker rejected the **username or password**. It is not caused by the random client ID that the client library generates. In a test with a real broker (`allow_anonymous false`), a wrong agent password gave `Not authorized`, and the correct password connected. Check:

1. The hub uses `MQTT_USERNAME=orb_hub` and its password; the agent uses `orb_agent` and its own password in `agent_windows/config.json`. Each user must exist in the password file.
2. You restarted Mosquitto after changing the password file or the config.
3. Test a login by hand, from `C:\Program Files\mosquitto\`: `.\mosquitto_sub.exe -h 127.0.0.1 -u orb_agent -P <password> -t test -v`

`allow_anonymous true` is acceptable for development **only while the listener is bound to `127.0.0.1`**. Set it back to `false` before letting other machines connect.
