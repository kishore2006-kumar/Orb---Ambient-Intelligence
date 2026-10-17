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
