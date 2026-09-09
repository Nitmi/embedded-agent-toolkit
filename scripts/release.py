#!/usr/bin/env python3
"""Build, verify, and install versioned toolkit plugins without hardware access."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True

if __package__:
    from . import component_install, component_lock, toolkit_doctor
else:
    import component_install
    import component_lock
    import toolkit_doctor

PLUGIN = "embedded-agent-toolkit"
SCHEMA = "embedded-agent-toolkit.release.v1"
MANIFEST = "release-manifest.json"
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_FILES = 512
REQUIRED_FILES = {
    "plugin.json",
    ".codex-plugin/plugin.json",
    "component-catalog.json",
    "LICENSE",
    "README.md",
    "scripts/bootstrap.py",
    "scripts/component_install.py",
    "scripts/release.py",
    "scripts/component_lock.py",
    "scripts/station_config.py",
    "scripts/toolkit_doctor.py",
    *(
        f"skills/{name}/SKILL.md"
        for name in (
            "embedded-bringup",
            "firmware-debug",
            "hardware-test",
            "incident-capture",
        )
    ),
}


class ReleaseError(ValueError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReleaseError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def json_object(data: bytes) -> dict:
    result = json.loads(data, object_pairs_hook=unique_object)
    if not isinstance(result, dict):
        raise ReleaseError("Expected a JSON object")
    return result


def safe_path(name: str) -> str:
    if not isinstance(name, str) or not name or len(name) > 512:
        raise ReleaseError("Invalid release path")
    for part in name.split("/"):
        if (
            not part
            or part in {".", ".."}
            or len(part) > 255
            or part.endswith((".", " "))
            or any(
                ord(char) < 32 or ord(char) > 126 or char in '\\:<>"|?*'
                for char in part
            )
            or re.fullmatch(
                r"(?i)(CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[0-9]|LPT[0-9])(?:\..*)?",
                part,
            )
        ):
            raise ReleaseError(f"Unsafe release path: {name}")
    return name


def validate_names(names: list[str]) -> None:
    folded = set()
    for name in names:
        key = safe_path(name).casefold()
        if key in folded:
            raise ReleaseError(f"Duplicate or case-colliding release path: {name}")
        folded.add(key)
    for key in folded:
        parts = key.split("/")
        if any("/".join(parts[:index]) in folded for index in range(1, len(parts))):
            raise ReleaseError(f"File/directory collision: {key}")


def release_version(files: dict[str, bytes]) -> str:
    if not REQUIRED_FILES.issubset(files):
        raise ReleaseError(
            f"Missing plugin files: {sorted(REQUIRED_FILES - files.keys())}"
        )
    versions = []
    for path in ("plugin.json", ".codex-plugin/plugin.json"):
        document = json_object(files[path])
        if document.get("name") != PLUGIN or document.get("skills") != "./skills/":
            raise ReleaseError(f"Invalid plugin identity or Skills location: {path}")
        if any(key in document for key in ("mcpServers", "apps", "hooks")):
            raise ReleaseError(
                "Aggregate releases must not register component services"
            )
        version = document.get("version")
        if not isinstance(version, str):
            raise ReleaseError("Missing plugin version")
        base = version.split("+codex.", 1)[0]
        if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", base):
            raise ReleaseError("Release version must be stable major.minor.patch")
        versions.append(base)
    if versions[0] != versions[1]:
        raise ReleaseError("Plugin manifest versions differ")
    try:
        component_install.parse_catalog(files["component-catalog.json"])
    except component_install.InstallError as error:
        raise ReleaseError(f"Invalid component catalog: {error}") from error
    if any(
        path.casefold() in {".mcp.json", "mcp.json", ".app.json", "hooks.json"}
        for path in files
    ):
        raise ReleaseError("Aggregate release contains an active service manifest")
    return versions[0]


def included(path: str) -> bool:
    return (
        path
        in {
            "plugin.json",
            ".codex-plugin/plugin.json",
            "component-catalog.json",
            "LICENSE",
            "README.md",
        }
        or path.startswith("skills/")
        or (path.startswith("docs/") and path != "docs/local-acceptance.md")
        or (path.startswith("scripts/") and path.endswith(".py"))
    )


def git_bytes(root: Path, *args: str) -> bytes:
    process = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, timeout=30, check=False
    )
    if process.returncode:
        raise ReleaseError(process.stderr.decode("utf-8", errors="replace").strip())
    return process.stdout


def source_snapshot(root: Path) -> tuple[str, dict[str, bytes]]:
    if git_bytes(root, "status", "--porcelain", "--untracked-files=normal").strip():
        raise ReleaseError("Commit the source changes before building a release")
    revision = git_bytes(root, "rev-parse", "HEAD").decode("ascii").strip()
    files = {}
    total = 0
    for entry in git_bytes(root, "ls-tree", "-r", "-z", "-l", revision).split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        path = raw_path.decode("utf-8")
        if not included(path):
            continue
        mode, kind, _, size = metadata.split()
        if mode not in {b"100644", b"100755"} or kind != b"blob":
            raise ReleaseError(f"Release source must be a regular file: {path}")
        total += int(size)
        if (
            int(size) > MAX_FILE_BYTES
            or total > MAX_TOTAL_BYTES
            or len(files) >= MAX_FILES - 1
        ):
            raise ReleaseError("Release source size or file count limit exceeded")
        # Read the commit, not checkout bytes affected by autocrlf or concurrent edits.
        files[safe_path(path)] = git_bytes(root, "show", f"{revision}:{path}")
    return revision, files


def make_archive(revision: str, source_files: dict[str, bytes]) -> tuple[str, bytes]:
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", revision):
        raise ReleaseError("Invalid source revision")
    files = dict(source_files)
    version = release_version(files)
    for path in ("plugin.json", ".codex-plugin/plugin.json"):
        document = json_object(files[path])
        document["version"] = version
        files[path] = json_bytes(document)
    validate_names([*files, MANIFEST])
    if len(files) > MAX_FILES - 1 or any(
        len(data) > MAX_FILE_BYTES for data in files.values()
    ):
        raise ReleaseError("Release file limit exceeded")
    if sum(map(len, files.values())) > MAX_TOTAL_BYTES - MAX_FILE_BYTES:
        raise ReleaseError("Release total size limit exceeded")
    manifest = {
        "schema_version": SCHEMA,
        "name": PLUGIN,
        "version": version,
        "source_revision": revision,
        "scope": "plugin_only_no_component_binaries",
        "files": [
            {"path": path, "size": len(data), "sha256": digest(data)}
            for path, data in sorted(files.items())
        ],
    }
    files[MANIFEST] = json_bytes(manifest)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for path, data in sorted(files.items()):
            info = zipfile.ZipInfo(f"{PLUGIN}/{path}", date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, data)
    payload = buffer.getvalue()
    if len(payload) > MAX_ARCHIVE_BYTES:
        raise ReleaseError("Archive size limit exceeded")
    return version, payload


def build_release(root: Path, output_dir: Path) -> dict:
    revision, files = source_snapshot(root)
    version, payload = make_archive(revision, files)
    archive = output_dir / f"{PLUGIN}-{version}.zip"
    checksum = archive.with_suffix(".zip.sha256")
    if archive.exists() or checksum.exists():
        raise ReleaseError(
            "Release output already exists; use a fresh output directory"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    with archive.open("xb") as handle:
        handle.write(payload)
    with checksum.open("xb") as handle:
        handle.write(f"{digest(payload)}  {archive.name}\n".encode("ascii"))
    return {
        "archive": str(archive.resolve()),
        "checksum": str(checksum.resolve()),
        "sha256": digest(payload),
        "version": version,
        "source_revision": revision,
    }


def check_release_tag(root: Path, tag: str) -> dict:
    revision, files = source_snapshot(root)
    version = release_version(files)
    expected = f"v{version}"
    if tag != expected:
        raise ReleaseError(f"Release tag must be exactly {expected}")
    tagged_revision = (
        git_bytes(root, "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}")
        .decode("ascii")
        .strip()
    )
    if tagged_revision != revision:
        raise ReleaseError("Release tag does not resolve to the checked-out commit")
    return {"tag": tag, "version": version, "source_revision": revision}


def read_bounded(path: Path, limit: int) -> bytes:
    if not path.is_file() or path.stat().st_size > limit:
        raise ReleaseError(f"Not a regular bounded file: {path}")
    with path.open("rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ReleaseError(f"File limit exceeded: {path}")
    return data


def verify_release(
    archive_path: Path, checksum_path: Path
) -> tuple[dict, dict[str, bytes]]:
    checksum = read_bounded(checksum_path, 1024).decode("ascii")
    match = re.fullmatch(r"([0-9a-fA-F]{64})  ([^\r\n/\\]+)\r?\n?", checksum)
    if not match or match[2] != archive_path.name:
        raise ReleaseError("Checksum must name this archive with one SHA-256 entry")
    payload = read_bounded(archive_path, MAX_ARCHIVE_BYTES)
    if digest(payload) != match[1].lower():
        raise ReleaseError("Archive SHA-256 does not match the supplied checksum")
    files = {}
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_FILES:
            raise ReleaseError("Archive entry limit exceeded")
        validate_names([entry.filename for entry in entries])
        if sum(entry.file_size for entry in entries) > MAX_TOTAL_BYTES:
            raise ReleaseError("Archive expansion limit exceeded")
        for entry in entries:
            mode = entry.external_attr >> 16
            if (
                entry.is_dir()
                or stat.S_IFMT(mode) not in {0, stat.S_IFREG}
                or entry.compress_type != zipfile.ZIP_STORED
                or entry.flag_bits & 1
                or entry.file_size > MAX_FILE_BYTES
            ):
                raise ReleaseError(f"Unsupported archive entry: {entry.filename}")
            prefix = f"{PLUGIN}/"
            if not entry.filename.startswith(prefix):
                raise ReleaseError("Archive must have exactly the named plugin root")
            with archive.open(entry) as handle:
                data = handle.read(MAX_FILE_BYTES + 1)
            if len(data) != entry.file_size or len(data) > MAX_FILE_BYTES:
                raise ReleaseError("Archive entry size mismatch")
            files[entry.filename[len(prefix) :]] = data
    if MANIFEST not in files:
        raise ReleaseError("Missing release manifest")
    manifest = json_object(files[MANIFEST])
    if (
        set(manifest)
        != {"schema_version", "name", "version", "source_revision", "scope", "files"}
        or manifest["schema_version"] != SCHEMA
        or manifest["name"] != PLUGIN
        or manifest["scope"] != "plugin_only_no_component_binaries"
        or not isinstance(manifest["source_revision"], str)
        or not re.fullmatch(
            r"(?:[0-9a-f]{40}|[0-9a-f]{64})", manifest["source_revision"]
        )
    ):
        raise ReleaseError("Unsupported release manifest")
    records = manifest["files"]
    if not isinstance(records, list) or not 1 <= len(records) < MAX_FILES:
        raise ReleaseError("Invalid release file inventory")
    expected = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != {"path", "size", "sha256"}:
            raise ReleaseError("Invalid release file record")
        path = safe_path(record["path"])
        if not included(path):
            raise ReleaseError(f"File is outside the plugin release layout: {path}")
        if path == MANIFEST or path in expected or path not in files:
            raise ReleaseError("Duplicate or missing inventory file")
        if (
            type(record["size"]) is not int
            or record["size"] != len(files[path])
            or record["sha256"] != digest(files[path])
        ):
            raise ReleaseError(f"Release file integrity mismatch: {path}")
        expected.add(path)
    if expected != files.keys() - {MANIFEST}:
        raise ReleaseError("Archive contains files outside its manifest")
    if release_version(files) != manifest["version"]:
        raise ReleaseError("Release and plugin versions differ")
    return manifest, files


def is_link(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    # Python 3.11 lacks Path.is_junction; all Windows reparse points are excluded.
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & 0x400
    )


def verify_installed(destination: Path, files: dict[str, bytes]) -> None:
    if is_link(destination) or not destination.is_dir():
        raise ReleaseError("Installed plugin is not a regular directory")
    actual = set()
    expected_dirs = {
        parent.as_posix()
        for name in files
        for parent in Path(name).parents
        if parent != Path(".")
    }
    for base, directories, names in os.walk(destination, followlinks=False):
        for name in directories:
            path = Path(base) / name
            if (
                is_link(path)
                or path.relative_to(destination).as_posix() not in expected_dirs
            ):
                raise ReleaseError(
                    "Installed plugin contains an unexpected directory or link"
                )
        for name in names:
            path = Path(base) / name
            if is_link(path):
                raise ReleaseError("Installed plugin contains a link or junction")
            name = path.relative_to(destination).as_posix()
            if name not in files or read_bounded(path, MAX_FILE_BYTES) != files[name]:
                raise ReleaseError(
                    f"Installed file differs; refusing to overwrite: {name}"
                )
            actual.add(name)
    if actual != files.keys():
        raise ReleaseError("Installed plugin is incomplete; refusing to overwrite")


def install_release(archive: Path, checksum: Path, install_root: Path) -> dict:
    manifest, files = verify_release(archive, checksum)
    root = install_root.resolve()
    version_dir = root / manifest["version"]
    if is_link(version_dir):
        raise ReleaseError("Version directory must not be a link or junction")
    destination = version_dir / PLUGIN
    if not destination.resolve().is_relative_to(root):
        raise ReleaseError("Installation destination escapes the selected root")
    if destination.exists() or is_link(destination):
        verify_installed(destination, files)
        status = "already_installed"
    else:
        version_dir.mkdir(parents=True, exist_ok=True)
        destination.mkdir(exist_ok=False)
        # Exclusive creation never merges into an existing version. Failed writes
        # leave the new, inactive directory for inspection, not an activated plugin.
        for name, data in sorted(files.items()):
            output = destination / name
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("xb") as handle:
                handle.write(data)
        verify_installed(destination, files)
        status = "installed"
    return {
        "status": status,
        "version": manifest["version"],
        "plugin_path": str(destination),
        "activated": False,
        "path_modified": False,
        "components_installed": False,
    }


def install_ready_release(
    archive: Path,
    checksum: Path,
    install_root: Path,
    lock_output: Path,
    selections: dict[str, str],
    timeout: float,
) -> dict:
    if not 0.1 <= timeout <= 30:
        raise ReleaseError("--timeout must be between 0.1 and 30 seconds")
    if set(selections) != set(component_lock.SPECS):
        raise ReleaseError("ready setup requires baud, blea, and debugger paths")
    if lock_output.exists() or lock_output.is_symlink():
        raise ReleaseError("component lock output already exists")

    installation = install_release(archive, checksum, install_root)
    created = False
    try:
        lock_report = component_lock.create(lock_output, selections, timeout)
        created = True
        locked = component_lock.parse_lock(lock_output)
        doctor = toolkit_doctor.build_report(
            toolkit_doctor.COMPONENTS,
            timeout,
            Path(installation["plugin_path"]),
            locked,
            "release_generated",
            lock_output,
            component_lock.sha256(lock_output),
        )
        if not doctor["complete"]:
            details = ", ".join(doctor["errors"] or doctor["warnings"])
            raise ReleaseError(f"strict component doctor failed: {details}")
    except component_lock.LockError as error:
        if created:
            lock_output.unlink(missing_ok=True)
        raise ReleaseError(str(error)) from error
    except Exception:
        if created:
            lock_output.unlink(missing_ok=True)
        raise

    return {
        **installation,
        "ready": True,
        "component_lock": lock_report,
        "doctor": doctor,
    }


def install_with_component_lock(
    archive: Path,
    checksum: Path,
    install_root: Path,
    lock: Path,
    timeout: float,
) -> dict:
    if not 0.1 <= timeout <= 30:
        raise ReleaseError("--timeout must be between 0.1 and 30 seconds")
    try:
        lock_report = component_lock.inspect(lock)
    except component_lock.LockError as error:
        raise ReleaseError(str(error)) from error
    installation = install_release(archive, checksum, install_root)
    doctor = toolkit_doctor.build_report(
        toolkit_doctor.COMPONENTS,
        timeout,
        Path(installation["plugin_path"]),
        lock_report["components"],
        "release_argument",
        lock,
        component_lock.sha256(lock),
    )
    if not doctor["complete"]:
        details = ", ".join(doctor["errors"] or doctor["warnings"])
        raise ReleaseError(f"strict component doctor failed: {details}")
    return {
        **installation,
        "ready": True,
        "component_lock": lock_report,
        "doctor": doctor,
    }


def install_with_catalog_components(
    archive: Path,
    checksum: Path,
    install_root: Path,
    component_install_root: Path,
    lock_output: Path,
    timeout: float,
) -> dict:
    if not 0.1 <= timeout <= 600:
        raise ReleaseError("--timeout must be between 0.1 and 600 seconds")
    if lock_output.exists() or lock_output.is_symlink():
        raise ReleaseError("component lock output already exists")

    try:
        platform_name = component_install.current_platform()
    except component_install.InstallError as error:
        raise ReleaseError(str(error)) from error
    installation = install_release(archive, checksum, install_root)
    plugin_path = Path(installation["plugin_path"]).resolve()
    if component_install_root.resolve().is_relative_to(plugin_path):
        raise ReleaseError(
            "component install root must be outside the plugin directory"
        )
    if lock_output.resolve().is_relative_to(plugin_path):
        raise ReleaseError("component lock output must be outside the plugin directory")
    created = False
    try:
        component_report = component_install.install(
            plugin_path / "component-catalog.json",
            component_install_root,
            lock_output,
            platform_name,
            timeout,
        )
        created = True
        locked = component_lock.parse_lock(lock_output)
        doctor = toolkit_doctor.build_report(
            toolkit_doctor.COMPONENTS,
            timeout,
            Path(installation["plugin_path"]),
            locked,
            "release_generated",
            lock_output,
            component_lock.sha256(lock_output),
        )
        if not doctor["complete"]:
            details = ", ".join(doctor["errors"] or doctor["warnings"])
            raise ReleaseError(f"strict component doctor failed: {details}")
    except component_install.InstallError as error:
        if created:
            lock_output.unlink(missing_ok=True)
        raise ReleaseError(str(error)) from error
    except component_lock.LockError as error:
        if created:
            lock_output.unlink(missing_ok=True)
        raise ReleaseError(str(error)) from error
    except Exception:
        if created:
            lock_output.unlink(missing_ok=True)
        raise

    return {
        **installation,
        "components_installed": True,
        "ready": True,
        "component_install": component_report,
        "component_lock": component_report["component_lock"],
        "doctor": doctor,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="package a clean committed source tree")
    build.add_argument(
        "--source", type=Path, default=Path(__file__).resolve().parents[1]
    )
    build.add_argument("--output-dir", type=Path, default=Path("dist"))
    tag = commands.add_parser("check-tag", help="bind an exact tag to plugin version")
    tag.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    tag.add_argument("--tag", required=True)
    for name in ("verify", "install"):
        subparser = commands.add_parser(name)
        subparser.add_argument("archive", type=Path)
        subparser.add_argument("--checksum", type=Path, required=True)
        if name == "install":
            subparser.add_argument("--install-root", type=Path, required=True)
            subparser.add_argument("--component-lock", type=Path)
            subparser.add_argument("--component-install-root", type=Path)
            subparser.add_argument("--lock-output", type=Path)
            subparser.add_argument("--baud")
            subparser.add_argument("--blea")
            subparser.add_argument("--debugger")
            subparser.add_argument("--timeout", type=float, default=5.0)
    for subparser in commands.choices.values():
        subparser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            data = build_release(args.source.resolve(), args.output_dir)
        elif args.command == "check-tag":
            data = check_release_tag(args.source.resolve(), args.tag)
        elif args.command == "verify":
            manifest, files = verify_release(args.archive, args.checksum)
            data = {
                "version": manifest["version"],
                "file_count": len(files),
                "source_revision": manifest["source_revision"],
                "integrity_verified": True,
                "publisher_authenticity_verified": False,
            }
        else:
            explicit_values = (args.baud, args.blea, args.debugger)
            if args.component_lock is not None and (
                args.component_install_root is not None
                or args.lock_output is not None
                or any(value is not None for value in explicit_values)
            ):
                raise ReleaseError(
                    "--component-lock cannot be combined with component installation "
                    "or new-lock options"
                )
            if args.component_install_root is not None and any(
                value is not None for value in explicit_values
            ):
                raise ReleaseError(
                    "--component-install-root cannot be combined with --baud, "
                    "--blea, or --debugger"
                )
            if args.component_lock is not None:
                data = install_with_component_lock(
                    args.archive,
                    args.checksum,
                    args.install_root,
                    args.component_lock,
                    args.timeout,
                )
            elif args.component_install_root is not None:
                if args.lock_output is None:
                    raise ReleaseError(
                        "--component-install-root requires --lock-output"
                    )
                data = install_with_catalog_components(
                    args.archive,
                    args.checksum,
                    args.install_root,
                    args.component_install_root,
                    args.lock_output,
                    args.timeout,
                )
            elif args.lock_output is not None or any(
                value is not None for value in explicit_values
            ):
                if args.lock_output is None or any(
                    value is None for value in explicit_values
                ):
                    raise ReleaseError(
                        "--lock-output, --baud, --blea, and --debugger are required together"
                    )
                data = install_ready_release(
                    args.archive,
                    args.checksum,
                    args.install_root,
                    args.lock_output,
                    {
                        "baud": args.baud,
                        "blea": args.blea,
                        "embedded-debugger": args.debugger,
                    },
                    args.timeout,
                )
            else:
                data = install_release(args.archive, args.checksum, args.install_root)
        report = {
            "schema_version": SCHEMA,
            "ok": True,
            "operation": args.command,
            "hardware_access": False,
            "data": data,
        }
    except (
        ReleaseError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        zipfile.BadZipFile,
        subprocess.SubprocessError,
        NotImplementedError,
        RuntimeError,
    ) as error:
        report = {
            "schema_version": SCHEMA,
            "ok": False,
            "operation": args.command,
            "hardware_access": False,
            "error": str(error),
        }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["ok"]:
        print(json.dumps(report["data"], indent=2))
    else:
        print(report["error"], file=sys.stderr)
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
