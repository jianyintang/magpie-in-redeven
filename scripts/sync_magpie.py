"""Update only the recommendation in the Magpie template from its official release."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import NamedTemporaryFile


IMAGE = "ghcr.io/yetone/magpie"
PLATFORMS = {"linux-amd64": "amd64", "linux-arm64": "arm64"}
INDEX_TYPES = {"application/vnd.oci.image.index.v1+json",
               "application/vnd.docker.distribution.manifest.list.v2+json"}
MANIFEST_TYPES = {"application/vnd.oci.image.manifest.v1+json",
                  "application/vnd.docker.distribution.manifest.v2+json"}
VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


def version_tuple(version):
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise ValueError("expected a stable numeric version (MAJOR.MINOR.PATCH)")
    return tuple(map(int, version.split(".")))


def release_version(release):
    tag = release.get("tag_name")
    if (release.get("draft") is not False or release.get("prerelease") is not False
            or not isinstance(tag, str) or not tag.startswith("v")):
        raise ValueError("expected a published, non-prerelease Magpie release")
    version_tuple(tag[1:])
    return tag[1:]


def inspect_image(reference, *options):
    return json.loads(subprocess.check_output(
        ["docker", "buildx", "imagetools", "inspect", reference, *options],
        timeout=90,
    ))


def resolve_artifacts(version):
    index = inspect_image(f"{IMAGE}:{version}", "--raw")
    if index.get("schemaVersion") != 2 or index.get("mediaType") not in INDEX_TYPES:
        raise ValueError(f"Magpie {version} has no supported multi-platform index")

    artifacts = {}
    for platform, arch in PLATFORMS.items():
        matches = [entry for entry in index["manifests"]
                   if entry.get("platform", {}).get("os") == "linux"
                   and entry.get("platform", {}).get("architecture") == arch]
        if len(matches) != 1:
            raise ValueError(f"Magpie {version} needs exactly one image for {platform}")
        manifest = matches[0]
        digest = manifest.get("digest", "")
        variants = ("", "v8") if arch == "arm64" else ("", "v1")
        if (manifest.get("mediaType") not in MANIFEST_TYPES or not DIGEST.fullmatch(digest)
                or manifest["platform"].get("variant", "") not in variants):
            raise ValueError(f"Magpie {version} has an invalid image descriptor for {platform}")
        # Resolve by digest (not by tag again), and check the image config as well as the index.
        config = inspect_image(f"{IMAGE}@{digest}", "--format", "{{json .Image}}")
        if config.get("os") != "linux" or config.get("architecture") != arch:
            raise ValueError(f"Magpie {version} image config does not match {platform}")
        artifacts[platform] = f"{IMAGE}:{version}@{digest}"
    return artifacts


def sync_template(path, release):
    template = json.loads(path.read_text(encoding="utf-8"))
    if (template.get("kind") != "redeven.service-template"
            or template.get("template_id") != "magpie"
            or template.get("service_family_id") != "magpie"
            or sorted(template.get("supported_platforms", [])) != sorted(PLATFORMS)
            or set(template.get("platform_artifacts", {})) != PLATFORMS.keys()
            or type(template.get("revision")) is not int or template["revision"] < 1):
        raise ValueError("template identity, revision, or platforms no longer match the updater")

    current = template["recommended_version"]
    latest = release_version(release)
    if version_tuple(latest) < version_tuple(current):
        print(f"Upstream {latest} is older than {current}; keeping the current recommendation.")
        return

    artifacts = resolve_artifacts(latest)
    if current == latest:
        if artifacts != template["platform_artifacts"]:
            raise ValueError(f"Magpie {latest} image digests changed; manual review required")
        print(f"Magpie {current} is already current; verified both pinned images.")
        return

    template.update(recommended_version=latest, platform_artifacts=artifacts,
                    revision=template["revision"] + 1)
    # Stage outside the template directory so a failed write never pollutes the bundle.
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent.parent,
                            delete=False) as staged:
        staged_path = Path(staged.name)
    try:
        staged_path.write_text(json.dumps(template, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
        staged_path.replace(path)
    finally:
        staged_path.unlink(missing_ok=True)
    print(f"Prepared Magpie {current} -> {latest} (template revision {template['revision']}).")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release", type=Path, help="GitHub latest-release API response (JSON)")
    args = parser.parse_args()
    manifest = Path(__file__).resolve().parents[1] / "templates/magpie/redeven-service-template.json"
    try:
        sync_template(manifest, json.loads(args.release.read_text(encoding="utf-8")))
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        sys.exit(f"Magpie template sync failed: {error}")


if __name__ == "__main__":
    main()
