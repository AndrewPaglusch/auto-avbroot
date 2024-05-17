#!/usr/bin/env python3

import subprocess
import shutil
import os
import sys
import logging
import requests
import re
import zipfile
import io

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

# Tool and file paths
custota_tool_path = './custota-tool'
avbroot_tool_path = './avbroot'
magisk_apk_path = 'magisk.apk'

# Device-specific
device_codename = 'husky'
magisk_preinit_device = 'sda10'

# Key and cert paths
ota_key_path = 'keys/ota.key'
ota_cert_path = 'keys/ota.crt'
avb_key_path = 'keys/avb.key'

# Temp storage locations
factory_ota_path = 'temp/ota.factory.zip'
patched_ota_path = 'temp/ota.patched.zip'

# Final output paths
htdocs_path = 'htdocs/graphene_husky_ota'
update_info_path = f'{htdocs_path}/{device_codename}.json'
final_ota_path = f'{htdocs_path}/ota.zip'
csig_path = f'{final_ota_path}.csig'

# GitHub repo details
custotatool_gh_repo = 'chenxiaolong/Custota'
custotatool_asset_regex = r'custota-tool-.*-x86_64-unknown-linux-gnu\.zip'

avbroot_gh_repo = 'chenxiaolong/avbroot'
avbroot_asset_regex = r'avbroot-.*-x86_64-unknown-linux-gnu\.zip'
avbroot_zip_file_regex = 'avbroot'

magiskapk_gh_repo = 'topjohnwu/Magisk'
magiskapk_asset_regex = 'Magisk-v.*\.apk'


class OTAException(Exception):
    pass

def get_latest_gh_release_url(repo, asset_regex):
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    response = requests.get(api_url)
    response.raise_for_status()
    release_info = response.json()

    for asset in release_info['assets']:
        if re.match(asset_regex, asset['name']):
            return asset['browser_download_url']

    raise ValueError("No file matching provided regex \"{asset_regex\" found in latest release assets")

def download_and_extract_file(zip_url, out_file_path, file_regex=None):
    logging.debug(f"Downloading file from GitHub to memory: {zip_url}...")
    response = requests.get(zip_url)
    response.raise_for_status()
    zip_data = io.BytesIO(response.content)

    logging.debug("Parsing ZIP contents to find file to extract...")
    with zipfile.ZipFile(zip_data, 'r') as zip:
        zip_contents = zip.infolist()

        # Determine which file to extract
        if file_regex:
            logging.debug(f"Looking for file matching regex: {file_regex}")
            matching_files = [info for info in zip_contents if re.match(file_regex, info.filename)]
            if not matching_files:
                raise ValueError(f"No file matching provided regex \"{file_regex}\" found in ZIP contents")
            file_info = matching_files[0]
        else:
            file_info = zip_contents[0]

        file_name = file_info.filename
        logging.debug(f"Extracting \"{file_name}\" to disk from ZIP (in-memory) to {out_file_path}...")

        with zip.open(file_info) as source_file:
            with open(out_file_path, 'wb') as target_file:
                target_file.write(source_file.read())

    return os.path.abspath(file_name)

def set_file_executable(file_path):
    logging.debug(f"Setting file \"{file_path}\" to executable...")
    os.chmod(file_path, 0o755)

# Download the latest OTA
def fetch_and_download_latest_ota():
    url = 'https://grapheneos.org/releases'
    pattern = rf'https://releases.grapheneos.org/{device_codename}-ota_update-20\d{{8}}\.zip'

    logging.info("Fetching the latest OTA URL from GrapheneOS...")
    response = requests.get(url)
    if response.status_code != 200:
        raise OTAException("Failed to fetch the releases page")

    # Extract the first matching URL
    matches = re.findall(pattern, response.text)
    if not matches:
        raise OTAException("No OTA URL found")

    latest_ota_url = matches[0]
    logging.info(f"Found latest OTA URL: {latest_ota_url}. Downloading to {factory_ota_path}...")

    # Download the latest OTA
    ota_response = requests.get(latest_ota_url)
    if ota_response.status_code != 200:
        raise OTAException("Failed to download the OTA")

    with open(factory_ota_path, 'wb') as f:
        f.write(ota_response.content)

    logging.info("Latest OTA downloaded successfully.")

# Re-sign OTA with our key
def resign_ota_with_custom_key():
    cmd = [
        avbroot_tool_path, 'ota', 'patch',
        '--input', factory_ota_path,
        '--key-avb', avb_key_path,
        '--key-ota', ota_key_path,
        '--cert-ota', ota_cert_path,
        '--magisk', magisk_apk_path,
        '--magisk-preinit-device', magisk_preinit_device,
        '--output', patched_ota_path, 
    ]

    logging.info(f"Re-signing OTA at {factory_ota_path} with custom key. Saving to {patched_ota_path}...")
    try:
        subprocess.run(cmd, check=True)
        logging.info("OTA re-signing completed successfully.")
    except Exception as e:
        raise OTAException("Failed to re-sign OTA: " + str(e))

    try:
        shutil.move(patched_ota_path, final_ota_path)
    except Exception as e:
        raise OTAException(f"Failed moving patched OTA from {patched_ota_path} to {final_ota_path}: {e}")

# Generate csig file
def generate_csig():
    cmd = [
        custota_tool_path, 'gen-csig', '--input', final_ota_path,
        '--key', ota_key_path, '--cert', ota_cert_path, '--output', csig_path
    ]
    logging.info(f"Generating csig file from patched OTA at {final_ota_path} using key at {ota_key_path} and cert at {ota_cert_path}. Saving to {csig_path}...")
    try:
        subprocess.run(cmd, check=True)
        logging.info("Csig file generated.")
    except Exception as e:
        raise OTAException(f"Failed to generate csig file for OTA at {final_ota_path}: {e}")

# Generate update info JSON
def generate_update_info():
    cmd = [
        custota_tool_path, 'gen-update-info', '--file', update_info_path,
        '--location', os.path.basename(final_ota_path)
    ]
    logging.info(f"Generating update info JSON from {final_ota_path} and saving to {update_info_path}...")
    try:
        subprocess.run(cmd, check=True)
        logging.info("Update info JSON generated.")
    except Exception as e:
        raise OTAException(f"Failed to generate info JSON file for OTA at {final_ota_path}: {e}")

# Download the latest custota-tool
def setup_custota_tool():
    try:
        logging.info("Fetching the latest custota-tool release URL from GitHub...")
        latest_release_url = get_latest_gh_release_url(custotatool_gh_repo, custotatool_asset_regex)
        logging.debug(f"Latest custota-tool release URL: \"{latest_release_url}\"")

        logging.info("Downloading latest custota-tool release...")
        file_path = download_and_extract_file(latest_release_url, custota_tool_path)
        logging.info("Latest custota-tool downloaded successfully.")

        set_file_executable(file_path)
    except Exception as e:
        raise OTAException("Failed to download and setup custota-tool: " + str(e))

# Download the latest avbroot tool
def setup_avbroot_tool():
    try:
        logging.info("Fetching the latest avbroot release URL from GitHub...")
        latest_release_url = get_latest_gh_release_url(avbroot_gh_repo, avbroot_asset_regex)
        logging.debug(f"Latest avbroot release URL: \"{latest_release_url}\"")

        logging.info("Downloading latest avbroot release...")
        file_path = download_and_extract_file(latest_release_url, avbroot_tool_path, file_regex=avbroot_zip_file_regex)
        logging.info("Latest avbroot downloaded successfully.")

        set_file_executable(file_path)
    except Exception as e:
        raise OTAException("Failed to download and setup avbroot: " + str(e))

# Download the latest Magisk APK
def setup_magisk_apk():
    try:
        logging.info("Fetching the latest Magisk release URL from GitHub...")
        latest_release_url = get_latest_gh_release_url(magiskapk_gh_repo, magiskapk_asset_regex)
        logging.debug(f"Latest Magisk release URL: \"{latest_release_url}\"")

        logging.info("Downloading latest Magisk release...")
        response = requests.get(latest_release_url)
        response.raise_for_status()
        with open(magisk_apk_path, 'wb') as file:
            file.write(response.content)

        logging.info("Latest Magisk APK downloaded successfully.")
    except Exception as e:
        raise OTAException("Failed to download and setup Magisk APK: " + str(e))

# Run the functions
def main():
    try:
        for func in [setup_custota_tool,
                     setup_avbroot_tool,
                     setup_magisk_apk,
                     fetch_and_download_latest_ota,
                     resign_ota_with_custom_key,
                     generate_csig,
                     generate_update_info]:
            func()
    except OTAException as e:
        logging.error(f"An error occurred on step {func.__name__}: " + str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()

