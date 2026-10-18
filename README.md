# dreo-protocol
ESPhome component for Dreo fans via the wifi module<>MCU serial protocol.

Read https://www.davidc.net/content/hacking-dreo-htf-018s-serial-protocol for a description of this project
and instructions, particularly noting the warning to make sure your fan uses this protocol before flashing it.

Some sample packet captures and a python decoder are in [protocol/](protocol/).

An example full configuration is available in [example-dreo-htf018s-esp32c3.yaml](example-dreo-htf018s-esp32c3.yaml).
This is based on replacing the existing module with an ESP32C3 supermini.

There is also an example configuration for flashing the original MBL01 module in
[example-dreo-htf018s-mbl01.yaml](example-dreo-htf018s-mbl01.yaml).
without even having to open the case. To do this, compile and download a Beken OTA image. Then put the wifi module
into OTA mode (hold the oscillation button for 5 seconds until the countdown ends), connect to the captive access point,
and visit http://192.168.0.1 and upload the file. I have tested this allows me to install a functioning ESPhome
although I haven't tested the fan functionality - although that should be fine 

## DR-HAF004S air circulator

The [MBL01 example](example-dreo-haf004s-mbl01.yaml) uses fan speed DP4 (1–9)
and an **Oscillation Mode** select on DP24: Off, Horizontal, Vertical, Both.
It does not reuse the tower fan's datapoint map. See the
[protocol notes, raw captures and test instructions](protocol/dr-haf004s/README.md)
for confirmed mappings, unknown fields and recovery limitations.

The parser skips bounds-checked string datapoint values (type `03`) rather
than aborting the report, so strings preceding speed/oscillation do not hide
those updates. Other unknown types retain their warning-and-stop behavior.
This is not general string-datapoint entity support.

## Tested models

| Model      | Type  | Module  | Config | Status |
|------------|-------|---------|--------|--------|
| DR-HAF004S | Air circulator | MBL01 (original) | [example-dreo-haf004s-mbl01.yaml](example-dreo-haf004s-mbl01.yaml) | Tested ESPHome on the original module: speed and four-state horizontal/vertical oscillation command/report round trips. Other features are not mapped. [Protocol findings and validation limits](protocol/dr-haf004s/README.md). |
| DR-HTF001S | Tower | -       | | Untested, but I believe this is an earlier version of HTF018S. Reports welcome. |
| DR-HTF004S | Tower | MBL02   | | Uses a different protocol, will not work. See [dreo-cloudcutter](https://github.com/ouaibe/dreo-cloudcutter) instead. |
| DR-HTF018S | Tower | MBL01 (original) | [example-dreo-htf018s-mbl01.yaml](example-dreo-htf018s-mbl01.yaml) | Tested ESPhome installs okay, not tested fan functionality. Reports welcome. |
| DR-HTF018S | Tower | ESP32C3 | [example-dreo-htf018s-esp32c3.yaml](example-dreo-htf018s-esp32c3.yaml) | Tested, works perfectly. |
| DR-HTF024S | Tower | MBL01 (original) | [example-dreo-htf024s-mbl01.yaml](example-dreo-htf024s-mbl01.yaml) | Untested but [may work](https://github.com/davidc/dreo-protocol/issues/1). |

Please report back successes or failures. Please be careful and always ensure you have a way to restore the original firmware
if needed (e.g. UART), I accept no responsibility for bricked devices!
