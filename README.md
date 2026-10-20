# Custom firmware for the Tuya TS0202 ZigBee PIR motion sensor

![ts0202](https://github.com/xaviergr/ts0202_pir_custom_firmware/assets/1671631/e6ab9248-b88a-4981-8ef2-86a3111c9bd8)

> **Fork note:** this is a fork of
> [xaviergr/ts0202_pir_custom_firmware](https://github.com/xaviergr/ts0202_pir_custom_firmware)
> focused on network reliability. See [Changes in this fork](#changes-in-this-fork)
> and [Updating an already flashed device](#updating-an-already-flashed-device).

A minimal ZigBee firmware for TLSR825x based PIR motion sensor devices.
The implementation is based on the ZigBee SDK examples provided by Telink, but
vastly simplified and cleaned up for maintainability and ease of development.

The firmware targets to support the ubiquitous AliExpress Tuya PIR motion sensors
that are sold under various names like ONENUO and AUBESS. Unfortunately, while
very competitively priced, all these devices are almost useless since you
can't really customize the occupied-to-unoccupied delay. Instead the occupied
state is cleared after a fixed 60 second delay from the moment the last movement
is detected by the PIR sensor.

This alternative firmware is pretty basic and supports the bare minimum:
 - Pairing (when first powering up or by holding the button for 5 seconds)
 - Reporting of remaining battery percentage
 - Customizable occupied to unoccupied delay

Features that are currently missing:
 - Touchlink
 - Identification
 - Binding and groups
 - Over the air updates (OTA)

The idle power consumption is minimized by utilizing the deep sleep mode of the
microcontroller and was measured to be around 13uA (vs 15.5uA for the original
firmware) for all tested devices.
(Upstream measurement. This fork sleeps in retention mode and wakes once per hour,
so idle current is expected to be slightly higher; it has not been re-measured.)

## Changes in this fork

**Device dropping off the network after ~4 hours of no motion (fixed)**
The device asks its parent for a 256 minute end device timeout, but when idle it
went to full deep sleep and only woke up on PIR/button. After ~4 hours without
motion the parent aged it out of its child table and the sensor became
unavailable. Now it always sleeps with retention and wakes up for the nearest
timer, so it sends a data poll to its parent at least once per hour.
(`src/main.c`, `src/app_cfg.h`)

**Device shown as unavailable in Home Assistant after 6 hours of no motion (fixed)**
ZHA marks a battery powered device unavailable when it hasn't heard from it for
6 hours (`consider_unavailable_battery`, 21600 s). The hourly data poll above
only goes to the parent router and never reaches the coordinator, so it doesn't
count. Now the current occupancy state is reported to the coordinator every
hour as a heartbeat. The value is unchanged, so no extra on/off entries show up
in the history. (`src/occupancy.c`)

**Battery percentage reported as uint8**
`BatteryPercentageRemaining` is a uint8 attribute in the ZCL spec but was sent
and served as uint16. (`src/clusters.c`, `src/battery.c`)

**Battery re-measured every 24 hours**
Since the device no longer reboots on every wake up, the battery level is
re-measured and reported (if changed) every 24 hours. (`src/battery.c`)

**Rejoin fixes** (`src/bdb_init.c`, `src/main.c`)
- Bug: every `REJOIN_FAILURE` posted a *new* repeating rejoin timer without
  cancelling the old one (`ev_timer_taskPost` always allocates a new timer).
  During a long coordinator outage the timers piled up, draining the battery
  and eventually exhausting the timer pool. Now only one timer exists.
- Exponential backoff: retry after 3, 6, 12, then every 15 minutes. It never
  gives up; the backoff resets after a successful rejoin.
- While waiting to rejoin, any wake up (motion, button, timer) triggers an
  immediate attempt, rate limited to once per minute. If someone is in the room
  when the coordinator comes back, the sensor reconnects within about a minute;
  otherwise within 15 minutes.

**Factory reset needs a 5 second button hold** (was 3 seconds) to avoid
accidental resets. (`src/button.c`)

## Supported devices

These little Tuya PIR devices come under various names and have many different variants.

As of now the following models have been tested and known to work:
 - TS0202 by _TZ3000_6ygjfyll
 - TS0202 by _TZ3040_bb6xaihh

Both devices utilize the BS-612 PIR sensor but they have a slightly different
PCB layout and different GPIO mappings.

In theory any device based on the Telink TLSR825x microcontroller should be
supported but if the layout of the PCB is different, slight modifications to the
firmware might be needed.

### TZ3000_6ygjfyll variant

[Back PCB layout](https://github.com/xaviergr/ts0202_pir_custom_firmware/assets/1671631/0a67bdb0-653e-4e34-9c7f-91f5806a6b56)

[Front PCB layout and wiring](https://github.com/xaviergr/ts0202_pir_custom_firmware/assets/1671631/c07b3cbc-5f7e-499f-b4ff-5234634219a5)

This variant is the better one since the ONTIME pin of the BS-612 sensor can be
configured via GPIOs for a minimum clear delay of around 4-5 seconds without any
hardware modifications.

### TZ3040_bb6xaihh variant

[Back PCB layout](https://github.com/xaviergr/ts0202_pir_custom_firmware/assets/1671631/c219fedf-c545-436c-b95c-70e964b369b3)

[Front PCB layout and wiring](https://github.com/xaviergr/ts0202_pir_custom_firmware/assets/1671631/d8d658d1-c19c-4a42-91ac-2a3dcc0bcd59)

Unfortunately this variant has a fixed voltage divider applied to the ONTIME pin
and without hardware modifications the clear delay is fixed to around 60 seconds.
To lower the minimum delay to around 3-4 seconds the highlighted resistor has
to be removed and then short the remaining pins.

## Occupied to unoccupied delay

![clear_delay](https://github.com/xaviergr/ts0202_pir_custom_firmware/assets/1671631/22819849-180d-4634-84fa-1194e8fb8759)

To adjust the clear delay, overwrite the pir_o_to_u_delay attribute of the
OccupancySensing cluster with your desired value in seconds, while the sensor
is not idle (press a button or move the device while writing the attribute).

## Compiling

To build the default TZ3000_6ygjfyll board variant:

```
git clone git@github.com:xaviergr/ts0202_pir_custom_firmware.git
cd ts0202_pir_custom_firmware
cmake -B build
cmake --build build/
```

For the TZ3040_bb6xaihh variant, run the following:
```
cmake -DBOARD_VARIANT=2 build/
cmake --build build/
```

If omitted, BOARD_VARIANT defaults to 1.
The output binary that can be flashed to the device is: 'build/ts0202.bin'

## Flashing

As of now the OTA update feature is not supported so flashing the firmware manually
is the only option. Luckily the flashing process only requires a USB to UART
adapter and to solder 4 wires. For more instructions on flashing refer to the
[TlsrComSwireWriter](https://github.com/pvvx/TlsrComSwireWriter) repository.

For the exact pin layout check the above linked photos for your board variant.

To flash the binary run the following commands:
```
.\TLSR825xComFlasher.py -p COM4 -t 100 ea
.\TLSR825xComFlasher.py -p COM4 -t 100 wf 0x0 path-to-ts0202.bin
```

Remember to always erase the entire flash (first command) before flashing the
binary. Make sure to adjust the 'COM4' port in the above example to whatever
serial port under Windows (COMx) or Linux (/dev/ttyUSBx) you are using.

## Updating an already flashed device

When the device already runs this firmware (upstream or this fork), you can
update it **without losing the ZigBee pairing and the configured
occupied-to-unoccupied delay**. Both are stored in the NV area at the top of
the flash, far above the ~110KB firmware image, and `wf` only erases the
sectors it writes.

**Do not run `ea`** for an update: it wipes the NV area, the delay goes back to
5 seconds and the device has to be paired again.

Tested with a CH340 USB-UART adapter and the wiring from
[TlsrComSwireWriter](https://github.com/pvvx/TlsrComSwireWriter)
(TX → 1.3kΩ → SWS, RX → SWS, GND → GND). Replace `COM21` with your port.

1. **Halt the chip.** Start the command below, then **briefly press the button a
   few times** within the 40 second window (don't hold it, a 5 second hold
   factory resets the device):
   ```
   python TLSR825xComFlasher.py -p COM21 -t 40000 rf 0 16 test.bin
   ```
   Power cycling did not work for us: with the adapter connected the chip
   stays powered through the TX line and the 1.3kΩ resistor, so it never
   resets. The button wakes it from deep sleep, which goes through the boot
   process where the flasher can catch it.
2. **Wake up the SPI flash.** If `test.bin` reads back as all `00`, the
   firmware left the flash in deep power-down mode. Copy
   [`tools/flash_wake_read.py`](tools/flash_wake_read.py) next to
   `TLSR825xComFlasher.py` and run it. It sends the release-from-power-down
   command (0xAB) and prints the first 64 bytes, which should no longer be zeros:
   ```
   python flash_wake_read.py COM21
   ```
3. **Write and verify** (the chip stays halted, so no `-t` is needed):
   ```
   python TLSR825xComFlasher.py -p COM21 -b 460800 wf 0 ts0202.bin
   python TLSR825xComFlasher.py -p COM21 rf 0 <size of ts0202.bin> readback.bin
   ```
   Compare `readback.bin` with `ts0202.bin` (e.g. `certutil -hashfile <file> SHA256`
   on Windows or `sha256sum` on Linux).
4. **Disconnect all wires** (not only VCC, see step 1), insert the battery
   and check in Home Assistant that the sensor is still paired and that the
   delay attribute kept its value.

Notes:
- Write at 460800 baud. At 921600 we saw bit errors in the written data.
- Do the activation (`-t`) at the default 921600 baud. At 460800 the CH340
  failed with `Write timeout` during activation.
