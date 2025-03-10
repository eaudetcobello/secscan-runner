# secscan-runner

The secscan-client snap provides scanning capabilities but lacks an abstraction to easily orchestrate multiple scans.

This is especially apparent in the Kubernetes team, where we have
a dozen images to scan. Submitting the scan, dealing with a flaky scan
API, retrieving results is time consuming.

This script tries to alleviate this burden by submitting scans concurrently
and handling retries when the API flakes.

## Usage

Install uv:

```
brew install uv
```

Run a scan:

```
uv run hello.py  --images-file images-new.yaml --output-dir output
```

The tool will create the output directory in the current folder. Then,
it will create an output/images directory where it downloads each image listed
in images.yaml. Once the images are downloaded, it will submit them for scanning using secscan-client and the Blackduck scanner. The tool saves
each scan's report, result and token in the output/$image folder where $image
is the OCI image name stripped of any tags and version numbers.

## Flags

```
Usage: hello.py [OPTIONS]

Options:
  --images-file TEXT  YAML file containing list of images to scan (defaults to ./images.yaml)
  --skip-export       Skip exporting images to tar files
  --skip-scan         Skip scanning with secscan-client
  --output-dir TEXT   Output directory for images, tokens and scans
  --help              Show this message and exit.
```

## Example output

```
.
├── hello.py
├── images.yaml
├── output
│   ├── cilium
│   │   ├── cilium.report
│   │   ├── cilium.result
│   ├── cilium-operator-generic
│   │   ├── cilium-operator-generic.report
│   │   ├── cilium-operator-generic.result
│   ├── coredns
│   │   ├── coredns.report
│   │   ├── coredns.result
│   ├── csi-node-driver-registrar
│   │   ├── csi-node-driver-registrar.report
│   │   ├── csi-node-driver-registrar.result
│   ├── csi-provisioner
│   │   ├── csi-provisioner.report
│   │   ├── csi-provisioner.result
│   ├── csi-resizer
│   │   ├── csi-resizer.report
│   │   ├── csi-resizer.result
│   ├── csi-snapshotter
│   │   ├── csi-snapshotter.report
│   │   ├── csi-snapshotter.result
│   ├── frr
│   │   ├── frr.report
│   │   ├── frr.result
│   ├── images
│   │   ├── cilium.image
│   │   ├── cilium-operator-generic.image
│   │   ├── coredns.image
│   │   ├── csi-node-driver-registrar.image
│   │   ├── csi-provisioner.image
│   │   ├── csi-resizer.image
│   │   ├── csi-snapshotter.image
│   │   ├── frr.image
│   │   ├── metallb-controller.image
│   │   ├── metallb-speaker.image
│   │   ├── metrics-server.image
│   │   ├── pause.image
│   │   ├── rawfile-localpv.image
│   ├── metallb-controller
│   │   ├── metallb-controller.report
│   │   ├── metallb-controller.result
│   ├── metallb-speaker
│   │   ├── metallb-speaker.report
│   │   ├── metallb-speaker.result
│   ├── metrics-server
│   │   ├── metrics-server.report
│   │   ├── metrics-server.result
│   ├── pause
│   │   ├── pause.report
│   │   ├── pause.result
│   ├── rawfile-localpv
│   │   ├── rawfile-localpv.report
│   │   ├── rawfile-localpv.result
│   └── tokens
│       ├── cilium-operator-generic.token
│       ├── cilium.token
│       ├── coredns.token
│       ├── csi-node-driver-registrar.token
│       ├── csi-provisioner.token
│       ├── csi-resizer.token
│       ├── csi-snapshotter.token
│       ├── frr.token
│       ├── metallb-controller.token
│       ├── metallb-speaker.token
│       ├── metrics-server.token
│       ├── pause.token
│       ├── rawfile-localpv.token
```
