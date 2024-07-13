# What Is This?

The purpose of this tool is to make installing OTA updates on GrapheneOS with [avbroot](https://github.com/chenxiaolong/avbroot) and [custota](https://github.com/chenxiaolong/Custota) as easy as possible. I originally wrote this for myself and for my specific needs, but I figured I'd open-source it and share it with everyone. It might be a bit opinionated in some areas because of this.

This tool does the following:
1) Downloads the latest avbroot, custota-tool, and Magisk APK
2) Downloads the latest OTA update of GrapheneOS for your phone
3) Uses `avbroot` to patch/re-sign the OTA with your custom key/certs (located in the `./keys` directory by default)
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
- You already know your [magisk preinit device](https://github.com/chenxiaolong/avbroot/blob/master/README.md#magisk-preinit-device) name
- You've [generated keys/certs for avbroot](https://github.com/chenxiaolong/avbroot#generating-keys)
- You have a public web directory that generated files can be dropped to (`--output-path`)

# Room for Improvement

The following are things that could be added to improve the efficiency and security of this script:
- Verify signature of all downloaded files where applicable
- Wrap this up in a Docker image with an embedded static web server.
  - Add a cron job to check to OTA updates and download/sign them automatically.
- Verify versions of avbroot, custota-tool, and Magisk so we only download the latest release if needed
- Verify latest OTA is newer than the one we have on disk (if one exists) before proceeding

Please submit a pull request if you've implemented any of the above.

# Usage

**Arguments**

NOTE: You can export `PASSWORD` as an environment variable instead of interactively providing it
```
./generate-ota.py
usage: generate-ota.py [-h] --device-codename DEVICE_CODENAME
                       --magisk-preinit-device MAGISK_PREINIT_DEVICE
                       [--ota-key-path OTA_KEY_PATH]
                       [--ota-cert-path OTA_CERT_PATH]
                       [--avb-key-path AVB_KEY_PATH] [--temp-path TEMP_PATH]
                       --output-path OUTPUT_PATH
generate-ota.py: error: the following arguments are required: --device-codename, --magisk-preinit-device, --output-path
```

**Generate the OTA**
```
./generate-ota.py --device-codename husky --magisk-preinit-device sda10 --output-path htdocs/graphene_husky_ota
Enter password:
2024-07-12 21:35:08,854 Fetching the latest custota-tool release URL from GitHub...
2024-07-12 21:35:09,096 Downloading latest custota-tool release...
2024-07-12 21:35:09,708 Latest custota-tool downloaded successfully.
2024-07-12 21:35:09,708 Fetching the latest avbroot release URL from GitHub...
2024-07-12 21:35:09,936 Downloading latest avbroot release...
2024-07-12 21:35:10,570 Latest avbroot downloaded successfully.
2024-07-12 21:35:10,570 Fetching the latest Magisk release URL from GitHub...
2024-07-12 21:35:10,797 Downloading latest Magisk release...
2024-07-12 21:35:11,493 Latest Magisk APK downloaded successfully.
2024-07-12 21:35:11,494 Fetching the latest OTA URL from GrapheneOS...
2024-07-12 21:35:11,754 Found latest OTA URL: https://releases.grapheneos.org/husky-ota_update-2024071200.zip
2024-07-12 21:35:11,774 Downloading the latest OTA to temp/husky_ota.factory.zip...
2024-07-12 21:35:30,412 Latest OTA downloaded successfully.
2024-07-12 21:35:30,413 Re-signing OTA at temp/husky_ota.factory.zip with custom key. Saving to temp/husky_ota.patched.zip...
  0.119s  INFO Replacing zip entry: META-INF/com/android/otacert
  0.119s  INFO Copying zip entry: apex_info.pb
  0.119s  INFO Copying zip entry: care_map.pb
  0.119s  INFO Patching zip entry: payload.bin
  0.119s  INFO Extracting from original payload: system
  6.721s  INFO Extracting from original payload: vbmeta
  6.722s  INFO Extracting from original payload: boot
  7.015s  INFO Extracting from original payload: init_boot
  7.094s  INFO Extracting from original payload: vendor_boot
  7.428s  INFO Patching boot images: boot, init_boot, vendor_boot
  9.995s  INFO Patching system image: system
 15.064s  INFO Patched otacerts.zip offsets in system: [599113728..599115688]
 15.064s  INFO Patching vbmeta images: vbmeta
 15.086s  INFO Compressing full image: vbmeta
 15.086s  INFO Compressing full image: vendor_boot
 16.635s  INFO Compressing full image: init_boot
 17.019s  INFO Compressing partial image: system: [599113728..599115688, 1241772032..1261454144, 1261764544..1261764608]
 23.947s  INFO Generating new OTA payload
 48.178s  INFO Patching zip entry: payload_properties.txt
 48.178s  INFO Generating new OTA metadata
 48.197s  INFO Verifying metadata offsets
 48.203s  INFO Successfully patched OTA
2024-07-12 21:36:18,642 OTA re-signing completed successfully.
2024-07-12 21:36:18,675 Generating csig file from patched OTA at htdocs/graphene_husky_ota/ota.zip using key at keys/ota.key and cert at keys/ota.crt. Saving to htdocs/graphene_husky_ota/ota.zip.csig...
Verifying OTA signature...
Device name: husky
Fingerprint: google/husky/husky:14/AP2A.240705.005/2024071200:user/release-keys
Security patch: 2024-07-05
Wrote: "htdocs/graphene_husky_ota/ota.zip.csig"
2024-07-12 21:36:30,752 Csig file generated.
2024-07-12 21:36:30,753 Generating update info JSON from htdocs/graphene_husky_ota/ota.zip and saving to htdocs/graphene_husky_ota/husky.json...
Updated: "htdocs/graphene_husky_ota/husky.json"
2024-07-12 21:36:30,758 Update info JSON generated.
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
