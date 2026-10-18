# DR-HAF004S / MBL01 findings

This is the **DR-HAF004S air circulator**, not the similarly named
DR-HTF004S tower fan. One original MBL01 module was tested with ESPHome
2026.9.1 / LibreTiny 1.13.0. The MBL01 label alone does not establish a shared
MCU datapoint map across models or revisions.

Use [the model-specific example](../../example-dreo-haf004s-mbl01.yaml).
It exposes fan power/speed and a four-state oscillation selector, without
capture buttons or UART-debug overhead. It deliberately does not copy
unverified tower fan controls for mode, display, beeper, timers, or temperature.

## What was tested

A person beside the fan operated the original IR remote and confirmed its
physical horizontal/vertical oscillation and displayed speed. An agent
collected raw UART data through ESPHome, reconstructed and checksum-validated
the frames, compared datapoints, implemented the fix, and ran replay/build
checks. This was not inferred solely from optimistic Home Assistant states.

- Horizontal on/off, vertical on/off, and both axes together were correlated
  with MCU reports: DP24 values 1/0, 2/0, and 3 respectively.
- Displayed speeds 1, 2, and 3 were correlated with DP4. A report containing 9
  was also captured, and the owner confirmed nine available speed settings.
  Every speed between 1 and 9 was **not** separately physically verified.
- During initial hardware bring-up, native API commands for speed 2 then 1,
  and oscillation Horizontal then Both, produced matching **MCU-reported**
  values. The submitted parser was subsequently narrowed to skip only strings;
  its code and default settings were deployed on that same fan (retaining only
  its existing identity/credentials and local source path). Version and state
  readback passed on the final build; command round trips were not repeated
  after that narrowing. These checks do not independently establish every
  motor's physical response to every Home Assistant command.
- Power was reported as on (DP1 boolean). Off/on commands were not separately
  exercised during this investigation.
- The patched firmware was compiled and installed on the original MBL01.
  The public example uses the same board, pins, flash layout and control
  mappings, but a new example node name and secret references.

## Framing and datapoints

The observed UART transport matches the framing already implemented here:
115200 baud, 8N1, big-endian values, and:

```text
55 AA version sequence command reserved length_hi length_lo payload checksum
```

`checksum = sum(header + payload) & 0xff`. A status report has command `07`.
Datapoints inside its payload have a **five-byte** header:

```text
id flags type length_hi length_lo value...
```

Flags in the supplied status fixtures are zero. Do not remove the flags byte
or parse these as ordinary four-byte-header Tuya datapoints.

### Why the tower example only partly worked

The status report includes **DP3, type `03`, a variable-length string** before
DP4 (speed) and DP24 (oscillation). The old parser returned from the *whole
report* when it encountered an unsupported type, so valid datapoints after
DP3 never reached their listeners. Turning up decoded logging alone cannot
recover values which the parser never reaches.

The fix recognizes string type `03`, checks the advertised length as before,
skips that string, and continues parsing. It does **not** treat a string as an
enum, notify numeric listeners for it, or add general string-entity support.
All other unknown types retain upstream's warning-and-stop behavior. Malformed
lengths still terminate the report safely. Existing numeric handling and
transmitted commands are unchanged.

### Observed inventory

IDs below are decimal. Observations are not automatically validated meanings.

| DP | Type | Observed value(s) | Interpretation / confidence |
|----|------|-------------------|-----------------------------|
| 1 | boolean (`01`) | true | Power reported on; no separate off/on write test |
| 2 | enum (`04`) | 1 | Unknown in these tests; **not** the tower's boolean display DP |
| 3 | string (`03`) | `temp:23333334444446666668888889` | Likely custom temperature/speed profile; not experimentally decoded |
| 4 | enum (`04`) | 1, 2, 3, 9 | Fan speed; displayed 1/2/3 correlated, nine settings owner-confirmed |
| 12 | boolean (`01`) | false | Unknown |
| 13 | integer (`02`, 4 bytes) | 80, 81 | Temperature candidate; unit/meaning not independently validated |
| 15 | integer (`02`, 4 bytes) | 0 | Unknown |
| 16 | integer (`02`, 4 bytes) | 0 | Unknown |
| 17 | boolean (`01`) | false | Unknown |
| 18 | integer (`02`, 4 bytes) | 0 | Unknown |
| 19 | boolean (`01`) | true | Unknown |
| 21 | boolean (`01`) | false | Unknown |
| 22 | string (`03`) | `0,0`, `-30,0` | Position-pair candidate; appears in reports after stopping an axis; units/axis order not validated |
| 23 | string (`03`) | `90,30,-30,-30` | Oscillation/cruise-configuration candidate; fields not validated |
| 24 | enum (`04`) | 0, 1, 2, 3 | Oscillation mode, all four states physically correlated |
| 25 | boolean (`01`) | false | Unknown |
| 26 | enum (`04`) | 2 | Unknown |

DP24's observed values are bit-compatible:

| Value | Horizontal | Vertical |
|-------|------------|----------|
| 0 | off | off |
| 1 | on | off |
| 2 | off | on |
| 3 | on | on |

The native fan oscillation control is one boolean. The example therefore uses
an explicit, non-optimistic **Off / Horizontal / Vertical / Both** select and
does not attach DP24 directly to `oscillation_datapoint`. Treating values 2
and 3 as booleans would lose axis information; writing 0/1 would not preserve
vertical oscillation. `NO_RESTORE` avoids replaying stored fan settings during
startup; the MCU remains authoritative.

### Command `0E`

The MCU also emits command `0E` around local changes. For example, payload
`02 01 04` was seen during both horizontal and vertical changes. Its fields
were not decoded, and it is not used as the control/state source. It is
important to capture it, but the generic "datapoints changing" log is not
itself a speed or oscillation value.

## Captures and regression tests

[status-reports.json](status-reports.json) contains representative **real,
complete MCU-to-module frames**, not regenerated examples: all four
oscillation modes, a report with the extra DP22 string, and speed reports.
Only appliance frames and expected numeric values are included; no Wi-Fi,
API, OTA credentials, IP addresses or device MAC addresses are included.
The `speed-9-observed` label distinguishes an observed report from an
explicitly labeled speed-2/speed-3 physical confirmation.

Run from the repository root, with Python 3 and a C++17 compiler installed:

```sh
python3 tests/test_datapoints.py
# Optional host sanitizers, on compilers/platforms which support them:
CXXFLAGS='-fsanitize=address,undefined -g' python3 tests/test_datapoints.py
```

The test extracts the real `Dreo::handle_datapoints_` implementation and its
datapoint types from the component, stubbing only ESPHome's surrounding
transport/log machinery. It checks frame lengths/checksums before replaying
the payloads. Additional cases cover unknown types, zero-length values,
truncation, ignored IDs, unchanged numeric decoding, and suppression of
unsupported values from numeric listeners. With the pre-fix parser, the
first captured report fails because speed after DP3 is lost.

This is a focused parser test, not a full UART/state-machine or hardware
simulator. The existing interactive `protocol/decode.py` still contains
tower-model names; do not use those labels as this model's mapping.

## Optional raw capture

The default example does not include instrumentation. For a temporary diagnostic
build, add `level: DEBUG` under `logger` and this block under the existing `uart`:

```yaml
  rx_buffer_size: 1024
  debug:
    direction: BOTH
    dummy_receiver: false
    after:
      bytes: 64
      timeout: 20ms
    sequence:
      - lambda: UARTDebug::log_hex(direction, bytes, ' ');
```

Save a short network-log capture while changing one remote setting at a time,
about five seconds apart. Record physical starting state and button presses.
`<<<` is MCU-to-module RX; `>>>` is module-to-MCU TX. Reassemble each direction
independently: logger chunks are not packet boundaries. Validate complete frame
lengths/checksums; network logs are not guaranteed lossless. Remove the diagnostic
block after testing instead of leaving detailed capture active indefinitely.

The component still sends startup queries/heartbeats and accepts HA commands;
this is not a passive sniffer. Avoid HA writes/automations during IR-only
correlation. Do not sweep unknown IDs or guessed values.

## Configuration and recovery limits

Provide `wifi_ssid`, `wifi_password`, `dreo_haf004s_api_key`,
`dreo_haf004s_ota_password`, and `dreo_haf004s_ap_password` in your private
`secrets.yaml`. The API key is a valid ESPHome encryption key; the fallback-AP
password must meet ESPHome's length requirements. Keep your node name and
credentials if updating an already-adopted ESPHome device.

The public `board_build.bkota` values are inherited from the upstream MBL01
example; they are firmware-packaging parameters, not your private ESPHome
API/OTA credentials. The board and flash-layout settings are for the tested
MBL01; verify other revisions before flashing.

The test unit already had ESPHome. Its original Dreo factory firmware was
not backed up, and restoring factory firmware was **not tested**. Beken
`.ota.rbl` containers, ESPHome UF2 OTA artifacts and full-flash images are not
interchangeable. Preserve a recoverable image and verify the upload path for
your currently installed firmware before changing it. This contribution does
not add or validate a new vendor-firmware installation/recovery procedure.

## Related evidence (not UART mappings)

- [Exact-model Home Assistant discussion](https://github.com/JeffSteinbok/hass-dreo/issues/13)
- [Exact-model Homebridge state dump](https://github.com/zyonse/homebridge-dreo/issues/6)
- [Original transport investigation](https://www.davidc.net/content/hacking-dreo-htf-018s-serial-protocol)

The cloud-side `oscmode` observations agree with our physical/UART mapping.
`fixedconf`, `cruiseconf` and `customconf` provide useful leads for the string
fields, but cloud property names alone do not establish UART DP IDs, units,
write formats, or complete feature support.
