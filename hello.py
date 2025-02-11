import click
import yaml
import asyncio
from loguru import logger
from pathlib import Path
from functools import wraps

OUTPUT_DIR = Path("output")
TOKEN_DIR = OUTPUT_DIR / "tokens"
IMAGE_DIR = OUTPUT_DIR / "images"


def coro(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper


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
        logger.error(f"Failed to run {cmd}")
        logger.error(stderr.decode())
        return 1, stderr
    else:
        logger.debug(f"Ran {cmd}")

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
            logger.error(f"!!! Failed to export {image}.")
    else:
        logger.info(f"File {image_path} already exists, skipping.")


async def run_scan(image: str):
    image_filename = get_image_filename(image)
    image_path = IMAGE_DIR / f"{image_filename}.image"

    if not image_path.exists():
        logger.info(f"Image {image_filename} does not exist, skipping scan.")
        return

    submit_scan_cmd = f"secscan-client submit --scanner blackduck --type container-image --format oci {image_path}"

    code, scan_token = await run_async(submit_scan_cmd)
    if code != 0:
        logger.error(f"!!! Failed to submit scan for {image}")
        return

    scan_token = scan_token.decode().strip().replace("Scan request submitted.", "")

    logger.info(f"Scan token for {image}: {scan_token}")

    # Write token to file
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    token_file = TOKEN_DIR / f"{image_filename}.token"
    _ = token_file.write_text(scan_token)

    wait_cmd = f"secscan-client wait --token {token_file}"

    code, _ = await run_async(wait_cmd)
    if code != 0:
        logger.error(f"!!! Failed to wait for scan for {image_filename}")
        return

    report_path = OUTPUT_DIR / f"{image_filename}/{image_filename}.report"
    report_cmd = f"secscan-client report --token {token_file}"

    code, output = await run_async(report_cmd)
    if code == 0:
        _ = report_path.write_text(output.decode())
    else:
        logger.error(f"!!! Failed to get report for {image}")
        return

    result_path = OUTPUT_DIR / f"{image_filename}/{image_filename}.result"
    result_cmd = f"secscan-client result --token {token_file}"

    code, _ = await run_async(result_cmd)
    if code == 0:
        _ = result_path.write_text(output.decode())
    else:
        logger.error(f"!!! Failed to get result for {image}")
        return


@click.command()
@click.option(
    "--images-file",
    help="YAML file containing list of images to scan",
    required=True,
    default="images.yaml",
)
@click.option(
    "--skip-export",
    help="Skip exporting images to tar files",
    is_flag=True,
)
@click.option(
    "--skip-scan",
    help="Skip scanning with secscan-client",
    is_flag=True,
)
@click.option(
    "--output-dir",
    help="Output directory for images, tokens and scans",
    required=False,
    default="output",
)
@coro
async def main(images_file: str, skip_export: bool, skip_scan: bool, output_dir: str):
    images: list[str] = []

    try:
        images = yaml.safe_load(open(images_file))["images"]
    except Exception as e:
        logger.error(f"Failed to read images from {images_file}: {e}")
        return

    if len(images) == 0:
        logger.error(f"No images found in {images_file}")
        return

    OUTPUT_DIR = Path(output_dir)

    # Create output directory named after image and version
    for image in images:
        if not OUTPUT_DIR.exists():
            logger.info(f"Creating output directory {OUTPUT_DIR}")
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        else:
            logger.info(f"Output directory {OUTPUT_DIR} already exists, skipping.")

        if not (OUTPUT_DIR / f"{get_image_filename(image)}").exists():
            logger.info(f"Creating directory for {get_image_filename(image)}")
            (OUTPUT_DIR / f"{get_image_filename(image)}").mkdir(
                parents=True, exist_ok=True
            )
        else:
            logger.info(
                f"Directory for {get_image_filename(image)} already exists, skipping."
            )

    if not skip_export:
        save_image_tasks = [save_image(image) for image in images]

        _ = await asyncio.gather(*save_image_tasks)

    if not skip_scan:
        run_scan_tasks = [run_scan(image) for image in images]

        _ = await asyncio.gather(*run_scan_tasks)

    logger.success("Done")


if __name__ == "__main__":
    # main is wrapped with coro, so we call it as a function even though it's a coroutine
    main()
