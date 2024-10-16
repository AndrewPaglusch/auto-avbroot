#!/usr/bin/env python3

import argparse
import getpass
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


class OTAException(Exception):
    pass


class Settings:
    def __init__(self, args):
        # Tool and file paths
        self.custota_tool_path = './custota-tool'
        self.avbroot_tool_path = './avbroot'
        self.magisk_apk_path = 'magisk.apk'

        # Device-specific
        self.device_codename = args.device_codename
        self.magisk_preinit_device = args.magisk_preinit_device

        # Mix avb and ota encryption password into env vars
        # taken from the PASSWORD env var, or user input
        self.env_vars = self._get_password()

        # Key and cert paths
        self.ota_key_path = args.ota_key_path
        self.ota_cert_path = args.ota_cert_path
        self.avb_key_path = args.avb_key_path

        # Temp storage locations
        self.factory_ota_path = f'{args.temp_path}/{self.device_codename}_ota.factory.zip'
        self.patched_ota_path = f'{args.temp_path}/{self.device_codename}_ota.patched.zip'

        # Final output paths
        self.htdocs_path = args.output_path
        self.update_info_path = f'{self.htdocs_path}/{self.device_codename}.json'
        self.final_ota_path = f'{self.htdocs_path}/ota.zip'
        self.csig_path = f'{self.final_ota_path}.csig'

        # GitHub repo details
        self.custotatool_gh_repo = 'chenxiaolong/Custota'
        self.custotatool_asset_regex = r'custota-tool-.*-x86_64-unknown-linux-gnu\.zip'

        self.avbroot_gh_repo = 'chenxiaolong/avbroot'
        self.avbroot_asset_regex = r'avbroot-.*-x86_64-unknown-linux-gnu\.zip'
        self.avbroot_zip_file_regex = 'avbroot'

        self.magiskapk_gh_repo = 'topjohnwu/Magisk'
        self.magiskapk_asset_regex = 'app-release.apk'

    def _get_password(self):
        password = os.environ.get("PASSWORD")
        if not password:
            password = getpass.getpass("Enter password: ")

        env_vars = os.environ.copy()
        env_vars['PASSPHRASE_AVB'] = password # avbroot
        env_vars['PASSPHRASE_OTA'] = password # avbroot
        env_vars['PASSPHRASE_ENV_VAR'] = password # custota-tool
        return env_vars


# Modify the parse_args function to return both args and settings
def parse_args():
    parser = argparse.ArgumentParser(description='Generate a signed OTA for GrapheneOS with custom keys')

    # Device-specific
    parser.add_argument('--device-codename', required=True, help='Device codename. ex: husky')
    parser.add_argument('--magisk-preinit-device', required=True, help='Magisk preinit device. ex: sda10')

    # Key and cert paths
    parser.add_argument('--ota-key-path', default='keys/ota.key', help='Path to your OTA key')
    parser.add_argument('--ota-cert-path', default='keys/ota.crt', help='Path to your OTA certificate')
    parser.add_argument('--avb-key-path', default='keys/avb.key', help='Path to your AVB key')

    # Temp storage location
    parser.add_argument('--temp-path', default='temp', help='Path where temp files will be stored')

    # Final output paths
    parser.add_argument('--output-path', required=True, help='Output directory. ex: htdocs/graphene_husky_ota')

    return parser.parse_args()

def get_latest_gh_release_url(repo, asset_regex):
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    response = requests.get(api_url)
    response.raise_for_status()
    release_info = response.json()

    for asset in release_info['assets']:
        if re.match(asset_regex, asset['name']):
            return asset['browser_download_url']

    raise ValueError(f"No file matching provided regex \"{asset_regex}\" found in latest release assets")

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
def fetch_and_download_latest_ota(settings: Settings):
    url = 'https://grapheneos.org/releases'
    pattern = rf'https://releases.grapheneos.org/{settings.device_codename}-ota_update-20\d{{8}}\.zip'

    logging.info("Fetching the latest OTA URL from GrapheneOS...")
    response = requests.get(url)
    if response.status_code != 200:
        raise OTAException("Failed to fetch the releases page")

    # Extract the first matching URL
    matches = re.findall(pattern, response.text)
    if not matches:
        raise OTAException("No OTA URL found")

    latest_ota_url = matches[0]
    logging.info(f"Found latest OTA URL: {latest_ota_url}")
    logging.info(f"Downloading the latest OTA to {settings.factory_ota_path}...")

    # Stream the latest OTA to disk
    response = requests.get(latest_ota_url, stream=True)

    if response.status_code != 200:
        raise Exception(f"Failed to download the OTA, status code: {response.status_code}")

    with open(settings.factory_ota_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192): 
            f.write(chunk)

    logging.info("Latest OTA downloaded successfully.")

# Re-sign OTA with our key
def resign_ota_with_custom_key(settings: Settings):
    cmd = [
        settings.avbroot_tool_path, 'ota', 'patch',
        '--input', settings.factory_ota_path,
        '--key-avb', settings.avb_key_path,
        '--key-ota', settings.ota_key_path,
        '--cert-ota', settings.ota_cert_path,
        '--pass-avb-env-var', 'PASSPHRASE_AVB',
        '--pass-ota-env-var' , 'PASSPHRASE_OTA',
        '--magisk', settings.magisk_apk_path,
        '--magisk-preinit-device', settings.magisk_preinit_device,
        '--output', settings.patched_ota_path, 
    ]

    logging.info(f"Re-signing OTA at {settings.factory_ota_path} with custom key. Saving to {settings.patched_ota_path}...")
    try:
        subprocess.run(cmd, env=settings.env_vars, check=True)
        logging.info("OTA re-signing completed successfully.")
    except Exception as e:
        raise OTAException("Failed to re-sign OTA: " + str(e))

    try:
        shutil.move(settings.patched_ota_path, settings.final_ota_path)
    except Exception as e:
        raise OTAException(f"Failed moving patched OTA from {settings.patched_ota_path} to {settings.final_ota_path}: {e}")

# Generate csig file
def generate_csig(settings: Settings):
    cmd = [
        settings.custota_tool_path, 'gen-csig',
        '--input', settings.final_ota_path,
        '--key', settings.ota_key_path,
        '--passphrase-env-var', 'PASSPHRASE_ENV_VAR',
        '--cert', settings.ota_cert_path,
        '--output', settings.csig_path
    ]

    logging.info(f"Generating csig file from patched OTA at {settings.final_ota_path} using key at {settings.ota_key_path} and cert at {settings.ota_cert_path}. Saving to {settings.csig_path}...")
    try:
        subprocess.run(cmd, env=settings.env_vars, check=True)
        logging.info("Csig file generated.")
    except Exception as e:
        raise OTAException(f"Failed to generate csig file for OTA at {settings.final_ota_path}: {e}")

# Generate update info JSON
def generate_update_info(settings: Settings):
    cmd = [
        settings.custota_tool_path, 'gen-update-info', '--file', settings.update_info_path,
        '--location', os.path.basename(settings.final_ota_path)
    ]
    logging.info(f"Generating update info JSON from {settings.final_ota_path} and saving to {settings.update_info_path}...")
    try:
        subprocess.run(cmd, env=settings.env_vars, check=True)
        logging.info("Update info JSON generated.")
    except Exception as e:
        raise OTAException(f"Failed to generate info JSON file for OTA at {settings.final_ota_path}: {e}")

# Download the latest custota-tool
def setup_custota_tool(settings: Settings):
    try:
        logging.info("Fetching the latest custota-tool release URL from GitHub...")
        latest_release_url = get_latest_gh_release_url(settings.custotatool_gh_repo, settings.custotatool_asset_regex)
        logging.debug(f"Latest custota-tool release URL: \"{latest_release_url}\"")

        logging.info("Downloading latest custota-tool release...")
        file_path = download_and_extract_file(latest_release_url, settings.custota_tool_path)
        logging.info("Latest custota-tool downloaded successfully.")

        set_file_executable(file_path)
    except Exception as e:
        raise OTAException("Failed to download and setup custota-tool: " + str(e))

# Download the latest avbroot tool
def setup_avbroot_tool(settings: Settings):
    try:
        logging.info("Fetching the latest avbroot release URL from GitHub...")
        latest_release_url = get_latest_gh_release_url(settings.avbroot_gh_repo, settings.avbroot_asset_regex)
        logging.debug(f"Latest avbroot release URL: \"{latest_release_url}\"")

        logging.info("Downloading latest avbroot release...")
        file_path = download_and_extract_file(latest_release_url, settings.avbroot_tool_path, file_regex=settings.avbroot_zip_file_regex)
        logging.info("Latest avbroot downloaded successfully.")

        set_file_executable(file_path)
    except Exception as e:
        raise OTAException("Failed to download and setup avbroot: " + str(e))

# Download the latest Magisk APK
def setup_magisk_apk(settings: Settings):
    try:
        logging.info("Fetching the latest Magisk release URL from GitHub...")
        latest_release_url = get_latest_gh_release_url(settings.magiskapk_gh_repo, settings.magiskapk_asset_regex)
        logging.debug(f"Latest Magisk release URL: \"{latest_release_url}\"")

        logging.info("Downloading latest Magisk release...")
        response = requests.get(latest_release_url)
        response.raise_for_status()
        with open(settings.magisk_apk_path, 'wb') as file:
            file.write(response.content)

        logging.info("Latest Magisk APK downloaded successfully.")
    except Exception as e:
        raise OTAException("Failed to download and setup Magisk APK: " + str(e))

# Run the functions
def main():
    settings = Settings(parse_args())

    try:
        for func in [setup_custota_tool,
                     setup_avbroot_tool,
                     setup_magisk_apk,
                     fetch_and_download_latest_ota,
                     resign_ota_with_custom_key,
                     generate_csig,
                     generate_update_info]:
            func(settings)
    except OTAException as e:
        logging.error(f"An error occurred on step {func.__name__}: " + str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()

