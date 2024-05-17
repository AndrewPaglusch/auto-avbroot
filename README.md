# What Is This?

The purpose of this tool is to make installing OTA updates on GrapheneOS with [avbroot](https://github.com/chenxiaolong/avbroot) and [custota](https://github.com/chenxiaolong/Custota) as easy as possible. I originally wrote this for myself and for my specific needs, but I figured I'd open-source it and share it with everyone. It might be a bit opinionated in some areas because of this.

This tool does the following:
1) Downloads the latest avbroot, custota-tool, and Magisk APK
2) Downloads the latest OTA update of GrapheneOS for your phone
3) Uses `avbroot` to patch/re-sign the OTA with your custom key/certs (located in the `./keys` directory)
4) Uses `custota-tool` to generate a `<devicename>.json` and `ota.zip.csig` file
5) Copies the `ota.zip` (avbroot-patched OTA), `<devicename>.json`, and `ota.zip.csig` file to a publicly-accessible directory

Custota, which should be installed as a Magisk module on your phone, will periodically check the public directory and notify/install new OTA updates as they're published.

This tool **does not** do the following:
- Root your phone
- Unlock your bootloader
- Install GrapheneOS
- Generate keys for avbroot

# Assumptions

The following assumptions are made. This script won't work if they're not true:
- Your phone is rooted
- GrapheneOS is installed already
- You've [generated keys/certs for avbroot](https://github.com/chenxiaolong/avbroot#generating-keys) and their names match what's configured in the script
- You have a `./htdocs` directory (or a symlink to one) that's public to the internet

# Usage

**Cleanup**
```
./cleanup.sh
Cleaning up...
removed 'temp/ota.factory.zip'
removed 'htdocs/graphene_husky_ota/husky.json'
removed 'htdocs/graphene_husky_ota/ota.zip'
removed 'htdocs/graphene_husky_ota/ota.zip.csig'
Finished
```

**Configure Script**

Open the script in a text editor and change the settings under the `device-specific` section.
Make sure to [use the correct value](https://github.com/chenxiaolong/avbroot/blob/master/README.md#magisk-preinit-device) for `magisk_preinit_device` or you could run into problems!

**Generate the OTA**
```
./generate-ota.py
2024-05-17 00:29:43,476 Fetching the latest custota-tool release URL from GitHub...
2024-05-17 00:29:43,795 Downloading latest custota-tool release...
2024-05-17 00:29:44,398 Latest custota-tool downloaded successfully.
2024-05-17 00:29:44,398 Fetching the latest avbroot release URL from GitHub...
2024-05-17 00:29:44,655 Downloading latest avbroot release...
2024-05-17 00:29:45,356 Latest avbroot downloaded successfully.
2024-05-17 00:29:45,356 Fetching the latest Magisk release URL from GitHub...
2024-05-17 00:29:45,611 Downloading latest Magisk release...
2024-05-17 00:29:46,363 Latest Magisk APK downloaded successfully.
2024-05-17 00:29:46,365 Fetching the latest OTA URL from GrapheneOS...
2024-05-17 00:29:46,651 Found latest OTA URL: https://releases.grapheneos.org/husky-ota_update-2024051500.zip. Downloading to temp/ota.factory.zip...
2024-05-17 00:30:28,636 Latest OTA downloaded successfully.
2024-05-17 00:30:28,735 Re-signing OTA at temp/ota.factory.zip with custom key. Saving to temp/ota.patched.zip...
Enter passphrase for "keys/avb.key":
Enter passphrase for "keys/ota.key":
  7.925s  INFO Replacing zip entry: META-INF/com/android/otacert
  7.925s  INFO Copying zip entry: apex_info.pb
  7.925s  INFO Copying zip entry: care_map.pb
  7.925s  INFO Patching zip entry: payload.bin
  7.926s  INFO Extracting from original payload: init_boot
  8.059s  INFO Extracting from original payload: system
 17.184s  INFO Extracting from original payload: vbmeta
 17.185s  INFO Extracting from original payload: vendor_boot
 17.622s  INFO Extracting from original payload: boot
 18.222s  INFO Patching boot images: boot, init_boot, vendor_boot
 20.877s  INFO Patching system image: system
 25.377s  INFO Patched otacerts.zip offsets in system: [581902336..581904296]
 25.377s  INFO Patching vbmeta images: vbmeta
 25.409s  INFO Compressing full image: init_boot
 25.836s  INFO Compressing full image: vbmeta
 25.837s  INFO Compressing full image: vendor_boot
 27.783s  INFO Compressing partial image: system: [581902336..581904296, 1187856384..1206686528, 1206984640..1206984704]
 34.219s  INFO Generating new OTA payload
 58.974s  INFO Patching zip entry: payload_properties.txt
 58.974s  INFO Generating new OTA metadata
 58.994s  INFO Verifying metadata offsets
 58.999s  INFO Successfully patched OTA
2024-05-17 00:31:27,769 OTA re-signing completed successfully.
2024-05-17 00:31:27,778 Generating csig file from patched OTA at htdocs/graphene_husky_ota/ota.zip using key at keys/ota.key and cert at keys/ota.crt. Saving to htdocs/graphene_husky_ota/ota.zip.csig...
Enter passphrase for "keys/ota.key":
Verifying OTA signature...
Device name: husky
Fingerprint: google/husky/husky:14/AP1A.240505.005/2024051500:user/release-keys
Security patch: 2024-05-05
Wrote: "htdocs/graphene_husky_ota/ota.zip.csig"
2024-05-17 00:31:43,642 Csig file generated.
2024-05-17 00:31:43,643 Generating update info JSON from htdocs/graphene_husky_ota/ota.zip and saving to htdocs/graphene_husky_ota/husky.json...
Updated: "htdocs/graphene_husky_ota/husky.json"
2024-05-17 00:31:43,647 Update info JSON generated.
```

# Example Docker Compose File

**Put this behind a proxy that terminates TLS!**

```yaml
version: "2.1"
services:
  caddy:
    container_name: caddy
    image: caddy:latest
    restart: always
    volumes:
      - ./caddy:/srv
    command: ["caddy", "file-server", "--access-log", "--listen", ":8080", "--root", "/srv"]
```
