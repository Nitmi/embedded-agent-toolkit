#!/usr/bin/env python3
"""Plan or install exact Toolkit component artifacts without hardware access."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import io
import json
import platform
import re
import stat
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

sys.dont_write_bytecode = True

if __package__:
    from . import component_lock
else:
    import component_lock

SCHEMA = "embedded-agent-toolkit.component-install.v1"
CATALOG_SCHEMA = "embedded-agent-toolkit.component-catalog.v1"
MAX_CATALOG_BYTES = 256 * 1024
MAX_DOWNLOAD_BYTES = 256 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 256
MAX_EXECUTABLE_BYTES = 128 * 1024 * 1024
HASH = re.compile(r"[0-9a-f]{64}")
VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
PLATFORMS = {
    ("windows", "x86_64"): "windows-x86_64",
    ("windows", "aarch64"): "windows-aarch64",
    ("linux", "x86_64"): "linux-x86_64",
    ("linux", "aarch64"): "linux-aarch64",
    ("macos", "x86_64"): "macos-x86_64",
    ("macos", "aarch64"): "macos-aarch64",
}
DOWNLOAD_HOSTS = {
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
}


class InstallError(ValueError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise InstallError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def parse_catalog(data: bytes) -> dict:
    if not data or len(data) > MAX_CATALOG_BYTES:
        raise InstallError("catalog is empty or oversized")
    try:
        payload = json.loads(data, object_pairs_hook=unique_object)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise InstallError(f"invalid catalog JSON: {error}") from error
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "components",
    }:
        raise InstallError("catalog fields differ")
    if payload["schema_version"] != CATALOG_SCHEMA:
        raise InstallError("unsupported catalog schema")
    components = payload["components"]
    if not isinstance(components, dict) or set(components) != set(component_lock.SPECS):
        raise InstallError("catalog component inventory differs")
    for name, record in components.items():
        if not isinstance(record, dict) or set(record) != {
            "repository",
            "version",
            "artifacts",
        }:
            raise InstallError(f"catalog component fields differ: {name}")
        repository = record["repository"]
        version = record["version"]
        artifacts = record["artifacts"]
        if not isinstance(repository, str) or not REPOSITORY.fullmatch(repository):
            raise InstallError(f"invalid component repository: {name}")
        if not isinstance(version, str) or not VERSION.fullmatch(version):
            raise InstallError(f"invalid component version: {name}")
        if not isinstance(artifacts, dict):
            raise InstallError(f"invalid component artifacts: {name}")
        for platform_name, artifact in artifacts.items():
            validate_artifact(name, repository, version, platform_name, artifact)
    return payload


def read_catalog(path: Path) -> tuple[dict, str]:
    if path.is_symlink() or not path.is_file():
        raise InstallError(f"catalog is not a regular file: {path}")
    data = path.read_bytes()
    return parse_catalog(data), sha256(data)


def validate_asset_path(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 512 or "\\" in value:
        raise InstallError("invalid artifact executable path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise InstallError("unsafe artifact executable path")
    if any(ord(char) < 32 or char in ':<>"|?*' for char in value):
        raise InstallError("unsafe artifact executable path")
    return value


def validate_url(value: object, repository: str, version: str) -> str:
    if not isinstance(value, str) or len(value) > 4096:
        raise InstallError("invalid artifact URL")
    parsed = urllib.parse.urlsplit(value)
    prefix = f"/{repository}/releases/download/v{version}/"
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in {None, 443}
        or not parsed.path.startswith(prefix)
        or parsed.query
        or parsed.fragment
    ):
        raise InstallError(
            "artifact URL must be the component's exact GitHub tag asset"
        )
    return value


def validate_artifact(
    name: str,
    repository: str,
    version: str,
    platform_name: object,
    artifact: object,
) -> None:
    if platform_name not in PLATFORMS.values():
        raise InstallError(f"unsupported artifact platform: {platform_name}")
    if not isinstance(artifact, dict) or set(artifact) != {
        "url",
        "sha256",
        "format",
        "executable",
    }:
        raise InstallError(f"artifact fields differ: {name}/{platform_name}")
    validate_url(artifact["url"], repository, version)
    if not isinstance(artifact["sha256"], str) or not HASH.fullmatch(
        artifact["sha256"]
    ):
        raise InstallError(f"invalid artifact hash: {name}/{platform_name}")
    if artifact["format"] != "zip":
        raise InstallError(f"unsupported artifact format: {name}/{platform_name}")
    validate_asset_path(artifact["executable"])


def current_platform() -> str:
    system = platform.system().lower()
    system = {"darwin": "macos"}.get(system, system)
    machine = platform.machine().lower()
    machine = {"amd64": "x86_64", "arm64": "aarch64"}.get(machine, machine)
    try:
        return PLATFORMS[(system, machine)]
    except KeyError as error:
        raise InstallError(f"unsupported host platform: {system}-{machine}") from error


def is_link(path: Path) -> bool:
    try:
        status = path.lstat()
    except FileNotFoundError:
        return False
    return path.is_symlink() or bool(
        getattr(status, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def destination_path(root: Path, name: str, version: str, asset_path: str) -> Path:
    if is_link(root):
        raise InstallError("component install root must not be a link or junction")
    executable = PurePosixPath(asset_path).name
    destination = root / name / version / executable
    resolved = destination.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise InstallError("component destination escapes install root")
    return resolved


def plan(catalog_path: Path, install_root: Path, platform_name: str) -> dict:
    catalog, catalog_hash = read_catalog(catalog_path)
    components = []
    for name, record in catalog["components"].items():
        artifact = record["artifacts"].get(platform_name)
        item = {
            "name": name,
            "repository": record["repository"],
            "version": record["version"],
            "platform": platform_name,
            "status": "available" if artifact else "unavailable",
        }
        if artifact:
            item.update(
                {
                    "url": artifact["url"],
                    "sha256": artifact["sha256"],
                    "destination": str(
                        destination_path(
                            install_root.resolve(),
                            name,
                            record["version"],
                            artifact["executable"],
                        )
                    ),
                }
            )
        components.append(item)
    return {
        "schema_version": SCHEMA,
        "ok": True,
        "operation": "plan",
        "catalog": str(catalog_path.resolve()),
        "catalog_sha256": catalog_hash,
        "platform": platform_name,
        "complete": all(item["status"] == "available" for item in components),
        "components": components,
        "network_access": False,
        "executables_started": False,
        "hardware_access": False,
        "path_modified": False,
    }


def safe_download_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in DOWNLOAD_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in {None, 443}
    ):
        raise InstallError("download redirected outside allowed HTTPS hosts")
    return value


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(
            req, fp, code, msg, headers, safe_download_url(newurl)
        )


def read_download(response, limit: int, timeout: float) -> bytes:
    result: dict[str, object] = {}

    def read_response() -> None:
        try:
            chunks = []
            total = 0
            while True:
                chunk = response.read(min(1024 * 1024, limit + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > limit:
                    raise InstallError("component artifact is oversized")
            result["data"] = b"".join(chunks)
        except (
            InstallError,
            OSError,
            http.client.HTTPException,
            urllib.error.URLError,
        ) as error:
            result["error"] = error

    worker = threading.Thread(target=read_response, daemon=True)
    worker.start()
    worker.join(max(0.0, timeout))
    if worker.is_alive():
        response.close()
        raise InstallError("component download exceeded its total timeout")
    if "error" in result:
        raise result["error"]
    return result["data"]


def download(url: str, timeout: float) -> bytes:
    deadline = time.monotonic() + timeout
    safe_download_url(url)
    opener = urllib.request.build_opener(SafeRedirect())
    request = urllib.request.Request(
        url, headers={"User-Agent": "embedded-agent-toolkit"}
    )
    with opener.open(request, timeout=timeout) as response:
        safe_download_url(response.geturl())
        length = response.headers.get("Content-Length")
        if length is not None and int(length) > MAX_DOWNLOAD_BYTES:
            raise InstallError("component artifact is oversized")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise InstallError("component download exceeded its total timeout")
        data = read_download(response, MAX_DOWNLOAD_BYTES, remaining)
    return data


def executable_from_zip(data: bytes, asset_path: str) -> bytes:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ARCHIVE_ENTRIES:
                raise InstallError("component archive has too many entries")
            names = [entry.filename for entry in entries]
            if len({name.casefold() for name in names}) != len(names):
                raise InstallError("component archive contains duplicate paths")
            matches = [entry for entry in entries if entry.filename == asset_path]
            if len(matches) != 1:
                raise InstallError("component executable is missing or duplicated")
            entry = matches[0]
            mode = entry.external_attr >> 16
            if entry.is_dir() or stat.S_IFMT(mode) == stat.S_IFLNK:
                raise InstallError("component executable is not a regular file")
            if entry.file_size <= 0 or entry.file_size > MAX_EXECUTABLE_BYTES:
                raise InstallError("component executable size is invalid")
            executable = archive.read(entry)
    except zipfile.BadZipFile as error:
        raise InstallError("invalid component ZIP") from error
    if len(executable) != entry.file_size:
        raise InstallError("component executable extraction is incomplete")
    return executable


def install_file(destination: Path, data: bytes) -> str:
    if is_link(destination):
        raise InstallError(f"component destination is a link: {destination}")
    if destination.exists():
        if (
            not destination.is_file()
            or destination.stat().st_size > MAX_EXECUTABLE_BYTES
            or destination.read_bytes() != data
        ):
            raise InstallError(f"component destination differs: {destination}")
        return "already_installed"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        stream.write(data)
    destination.chmod(destination.stat().st_mode | stat.S_IXUSR)
    return "installed"


def write_lock(output: Path, components: dict[str, dict[str, str]]) -> dict:
    if output.exists() or is_link(output):
        raise InstallError("component lock output already exists")
    data = (
        json.dumps(
            {"schema_version": component_lock.SCHEMA, "components": components},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(data)
    try:
        component_lock.parse_lock(output)
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return {
        "path": str(output.resolve()),
        "sha256": sha256(data),
        "components": components,
    }


def install(
    catalog_path: Path,
    install_root: Path,
    lock_output: Path,
    platform_name: str,
    timeout: float,
) -> dict:
    if not 0.1 <= timeout <= 600:
        raise InstallError("--timeout must be between 0.1 and 600 seconds")
    proposed = plan(catalog_path, install_root, platform_name)
    if not proposed["complete"]:
        unavailable = [
            item["name"]
            for item in proposed["components"]
            if item["status"] == "unavailable"
        ]
        raise InstallError(
            f"catalog has no {platform_name} artifact for: {', '.join(unavailable)}"
        )
    if lock_output.exists() or is_link(lock_output):
        raise InstallError("component lock output already exists")
    catalog, _ = read_catalog(catalog_path)
    statuses = []
    locked = {}
    for item in proposed["components"]:
        name = item["name"]
        record = catalog["components"][name]
        artifact = record["artifacts"][platform_name]
        archive = download(artifact["url"], timeout)
        if sha256(archive) != artifact["sha256"]:
            raise InstallError(f"component artifact hash differs: {name}")
        executable = executable_from_zip(archive, artifact["executable"])
        destination = Path(item["destination"])
        status = install_file(destination, executable)
        identity = component_lock.identify(name, str(destination), timeout)
        if identity["version"] != record["version"]:
            raise InstallError(f"component version differs: {name}")
        locked[name] = identity
        statuses.append({**item, "status": status})
    lock = write_lock(lock_output, locked)
    return {
        "schema_version": SCHEMA,
        "ok": True,
        "operation": "install",
        "catalog": proposed["catalog"],
        "catalog_sha256": proposed["catalog_sha256"],
        "platform": platform_name,
        "components": statuses,
        "component_lock": lock,
        "network_access": True,
        "executables_started": True,
        "executed_command": "--version only",
        "hardware_access": False,
        "path_modified": False,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    for name in ("plan", "install"):
        command = commands.add_parser(name)
        command.add_argument(
            "--catalog",
            type=Path,
            default=Path(__file__).resolve().parents[1] / "component-catalog.json",
        )
        command.add_argument("--install-root", type=Path, required=True)
        command.add_argument("--platform", choices=sorted(PLATFORMS.values()))
        command.add_argument("--json", action="store_true")
        if name == "install":
            command.add_argument("--lock-output", type=Path, required=True)
            command.add_argument("--timeout", type=float, default=15.0)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        platform_name = args.platform or current_platform()
        if args.operation == "plan":
            report = plan(args.catalog, args.install_root, platform_name)
        else:
            report = install(
                args.catalog,
                args.install_root,
                args.lock_output,
                platform_name,
                args.timeout,
            )
    except (
        InstallError,
        OSError,
        UnicodeError,
        ValueError,
        subprocess.SubprocessError,
        urllib.error.URLError,
    ) as error:
        report = {
            "schema_version": SCHEMA,
            "ok": False,
            "operation": args.operation,
            "hardware_access": False,
            "error": str(error),
        }
    if args.json or report["ok"]:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(report["error"], file=sys.stderr)
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
