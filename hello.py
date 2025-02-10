import asyncio
from pathlib import Path
from typing import Tuple

images = [
    "ghcr.io/canonical/cilium-operator-generic:1.16.3-ck0",
    "ghcr.io/canonical/cilium:1.16.3-ck0",
    "ghcr.io/canonical/coredns:1.11.3-ck0",
    "ghcr.io/canonical/frr:9.1.0",
    "ghcr.io/canonical/k8s-snap/pause:3.10",
    "ghcr.io/canonical/k8s-snap/sig-storage/csi-node-driver-registrar:v2.10.1",
    "ghcr.io/canonical/k8s-snap/sig-storage/csi-provisioner:v5.0.1",
    "ghcr.io/canonical/k8s-snap/sig-storage/csi-resizer:v1.11.1",
    "ghcr.io/canonical/k8s-snap/sig-storage/csi-snapshotter:v8.0.1",
    "ghcr.io/canonical/metallb-controller:v0.14.8-ck0",
    "ghcr.io/canonical/metallb-speaker:v0.14.8-ck0",
    "ghcr.io/canonical/metrics-server:0.7.2-ck0",
    "ghcr.io/canonical/rawfile-localpv:0.8.1",
]

OUTPUT_DIR = Path("output")
TOKEN_DIR = OUTPUT_DIR / "tokens"
IMAGE_DIR = OUTPUT_DIR / "images"


def get_image_filename(image: str):
    return image.split("/")[-1].split(":")[0]


async def run_async(cmd: str) -> tuple[int, bytes]:
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        print(f"Failed to run {cmd}")
        print(stderr.decode())
        return 1, stderr
    else:
        print(f"Ran {cmd}")

    return 0, stdout


async def save_image(image: str):
    image_filename = get_image_filename(image)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    image_path = IMAGE_DIR / f"{image_filename}.image"

    if not image_path.exists():
        save_cmd = f"regclient.regctl image export {image}"
        code, output = await run_async(save_cmd)
        if code == 0:
            _ = image_path.write_bytes(output)
        else:
            print(f"!!! Failed to export {image}.")
    else:
        print(f"File {image_path} already exists, skipping.")


async def run_scan(image: str):
    image_filename = get_image_filename(image)
    image_path = IMAGE_DIR / f"{image_filename}.image"

    if not image_path.exists():
        print(f"Image {image_filename} does not exist, skipping scan.")
        return

    submit_scan_cmd = f"secscan-client submit --scanner blackduck --type container-image --format oci {image_path}"

    code, scan_token = await run_async(submit_scan_cmd)
    if code != 0:
        print(f"!!! Failed to submit scan for {image}")
        return

    scan_token = scan_token.decode().strip().replace("Scan request submitted.", "")

    print(f"Scan token for {image}: {scan_token}")

    # Write token to file
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    token_file = TOKEN_DIR / f"{image_filename}.token"
    _ = token_file.write_text(scan_token)

    wait_cmd = f"secscan-client wait --token {token_file}"

    code, _ = await run_async(wait_cmd)
    if code != 0:
        print(f"!!! Failed to wait for scan for {image_filename}")
        return

    report_path = OUTPUT_DIR / f"{image_filename}/{image_filename}.report"
    report_cmd = f"secscan-client report --token {token_file}"

    code, output = await run_async(report_cmd)
    if code == 0:
        _ = report_path.write_text(output.decode())
    else:
        print(f"!!! Failed to get report for {image}")
        return

    result_path = OUTPUT_DIR / f"{image_filename}/{image_filename}.result"
    result_cmd = f"secscan-client result --token {token_file}"

    code, _ = await run_async(result_cmd)
    if code == 0:
        _ = result_path.write_text(output.decode())
    else:
        print(f"!!! Failed to get result for {image}")
        return


async def main():
    # Create output directory named after image and version
    for image in images:
        print(f"Creating directory for {get_image_filename(image)}")
        # Create directory
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / f"{get_image_filename(image)}").mkdir(parents=True, exist_ok=True)

    save_image_tasks = [save_image(image) for image in images]

    _ = await asyncio.gather(*save_image_tasks)

    run_scan_tasks = [run_scan(image) for image in images]

    _ = await asyncio.gather(*run_scan_tasks)

    print("Done")


if __name__ == "__main__":
    asyncio.run(main())
