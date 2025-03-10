import click
import yaml
import asyncio
import time
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


async def run_async(cmd: str, max_retries=3, retry_delay=5) -> tuple[int, bytes]:
    """Run a command with retry logic for transient failures."""
    retries = 0
    while retries <= max_retries:
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            stderr_text = stderr.decode()
            logger.error(f"Failed to run {cmd}")
            logger.error(stderr_text)

            # Check if this is a 400 bad request that might be due to timing
            if "400" in stderr_text and retries < max_retries:
                retries += 1
                logger.warning(
                    f"Received 400 error, retrying {retries}/{max_retries} in {retry_delay} seconds..."
                )
                await asyncio.sleep(retry_delay)
                continue
            return 1, stderr
        else:
            logger.debug(f"Ran {cmd}")
            return 0, stdout

    # If we've exhausted retries
    return 1, b"Max retries exceeded"


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

    # Verify the image file is valid
    if image_path.stat().st_size == 0:
        logger.error(f"Image file {image_path} is empty, skipping scan.")
        return

    # Create the token directory if it doesn't exist yet
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    token_file = TOKEN_DIR / f"{image_filename}.token"

    submit_scan_cmd = f"secscan-client submit --scanner blackduck --type container-image --format oci {image_path}"
    logger.info(f"Submitting scan for {image}")

    code, scan_token = await run_async(submit_scan_cmd)
    if code != 0:
        logger.error(f"!!! Failed to submit scan for {image}")
        return

    scan_token_text = scan_token.decode().strip()
    scan_token_text = scan_token_text.replace("Scan request submitted.", "").strip()

    if not scan_token_text:
        logger.error(
            f"Empty scan token received for {image}, skipping further processing"
        )
        return

    logger.info(f"Scan token for {image}: {scan_token_text}")

    # Write token to file
    try:
        _ = token_file.write_text(scan_token_text)
    except Exception as e:
        logger.error(f"Failed to write token to file: {e}")
        return

    # Add a small delay to ensure token is fully processed by the system
    await asyncio.sleep(1)

    wait_cmd = f"secscan-client wait --token {token_file}"
    logger.info(f"Waiting for scan to complete for {image}")

    code, _ = await run_async(wait_cmd, max_retries=5, retry_delay=10)
    if code != 0:
        logger.error(f"!!! Failed to wait for scan for {image_filename}")
        return

    # Ensure output directory exists
    image_output_dir = OUTPUT_DIR / f"{image_filename}"
    image_output_dir.mkdir(parents=True, exist_ok=True)

    report_path = image_output_dir / f"{image_filename}.report"
    report_cmd = f"secscan-client report --token {token_file}"
    logger.info(f"Retrieving report for {image}")

    code, report_output = await run_async(report_cmd)
    if code == 0:
        try:
            _ = report_path.write_text(report_output.decode())
            logger.info(f"Report saved to {report_path}")
        except Exception as e:
            logger.error(f"Failed to write report: {e}")
    else:
        logger.error(f"!!! Failed to get report for {image}")
        return

    result_path = image_output_dir / f"{image_filename}.result"
    result_cmd = f"secscan-client result --token {token_file}"
    logger.info(f"Retrieving result for {image}")

    code, result_output = await run_async(result_cmd)
    if code == 0:
        try:
            _ = result_path.write_text(result_output.decode())
            logger.info(f"Result saved to {result_path}")
        except Exception as e:
            logger.error(f"Failed to write result: {e}")
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

    global OUTPUT_DIR, TOKEN_DIR, IMAGE_DIR
    OUTPUT_DIR = Path(output_dir)
    TOKEN_DIR = OUTPUT_DIR / "tokens"
    IMAGE_DIR = OUTPUT_DIR / "images"

    logger.info(f"Using output directory: {OUTPUT_DIR}")

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
