#!/usr/bin/env python3
"""
Debian / Ubuntu Package Builder for info-weather (.deb).

Produces a fully compliant Debian package without requiring root privileges.
Can use system `dpkg-deb` if available, or a pure-Python AR/tar builder for
cross-platform package generation (Windows, macOS, Linux).

Usage:
    python packaging/scripts/build_deb.py
    python packaging/scripts/build_deb.py --version 0.1.0 --release 1 --output-dir dist/
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


def get_project_root() -> Path:
    """Resolve repository root directory."""
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").is_file():
            return parent
    return Path.cwd()


def load_project_metadata(project_root: Path) -> dict[str, str]:
    """Extract project metadata from pyproject.toml."""
    pyproject_path = project_root / "pyproject.toml"
    meta = {
        "name": "info-weather",
        "version": "0.1.0",
        "description": "Modern desktop weather widget for Linux (KDE Plasma) with consensus providers",
        "homepage": "https://github.com/aimakosi/info-weather",
        "license": "GPL-3.0-or-later",
        "maintainer": "aimakosi <aimakosi@users.noreply.github.com>",
    }

    if pyproject_path.is_file():
        try:
            import tomllib
        except ModuleNotFoundError:  # Python < 3.11
            import tomli as tomllib
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
            proj = data.get("project", {})
            if "name" in proj:
                meta["name"] = str(proj["name"])
            if "version" in proj:
                meta["version"] = str(proj["version"])
            if "description" in proj:
                meta["description"] = str(proj["description"])
            if "license" in proj and isinstance(proj["license"], dict):
                meta["license"] = str(proj["license"].get("text", meta["license"]))

    return meta


def copy_tree_filtered(src: Path, dst: Path) -> None:
    """Copy directory recursively excluding bytecode and caches."""
    dst.mkdir(parents=True, exist_ok=True)
    for root, dirs, files in os.walk(src):
        # Exclude unwanted directories
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".pytest_cache", ".git", ".idea", ".vscode")]
        rel = Path(root).relative_to(src)
        target_dir = dst / rel
        target_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            if f.endswith((".pyc", ".pyo", ".swp", ".bak", ".tmp", "~")) or f == "Thumbs.db":
                continue
            src_file = Path(root) / f
            dst_file = target_dir / f
            shutil.copy2(src_file, dst_file)


def calculate_md5(file_path: Path) -> str:
    """Calculate MD5 hash of a file for Debian md5sums."""
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def create_tar_archive(source_dir: Path, out_tar_path: Path, prefix: str = ".") -> None:
    """Create normalized tar.gz archive with root:root ownership and reproducible permissions."""
    with tarfile.open(out_tar_path, "w:gz", format=tarfile.PAX_FORMAT) as tar:
        for root, dirs, files in os.walk(source_dir):
            dirs.sort()
            files.sort()
            rel_dir = Path(root).relative_to(source_dir)

            # Add directory entry
            if str(rel_dir) != ".":
                tar_dir_name = f"{prefix}/{rel_dir.as_posix()}"
                ti = tar.gettarinfo(root, arcname=tar_dir_name)
                ti.uid = 0
                ti.gid = 0
                ti.uname = "root"
                ti.gname = "root"
                ti.mode = 0o755
                ti.mtime = 1700000000  # reproducible timestamp
                tar.addfile(ti)

            # Add file entries
            for f in files:
                file_path = Path(root) / f
                rel_file = file_path.relative_to(source_dir)
                tar_file_name = f"{prefix}/{rel_file.as_posix()}"

                ti = tar.gettarinfo(str(file_path), arcname=tar_file_name)
                ti.uid = 0
                ti.gid = 0
                ti.uname = "root"
                ti.gname = "root"
                ti.mtime = 1700000000

                # Determine file executable permission
                if file_path.name in ("info-weather", "install_kwinrule.sh", "install.sh", "uninstall.sh") or \
                   file_path.name in ("postinst", "postrm", "prerm", "preinst") or \
                   file_path.suffix == ".py" and file_path.name == "main.py":
                    ti.mode = 0o755
                else:
                    ti.mode = 0o644

                with open(file_path, "rb") as fp:
                    tar.addfile(ti, fp)


def build_deb_pure_python(stage_dir: Path, deb_output_path: Path) -> None:
    """
    Assemble a standard Debian package file (.deb) using Unix ar format.
    Standard Debian package member order:
      1. debian-binary  (2.0\n)
      2. control.tar.gz (metadata, scripts, md5sums)
      3. data.tar.gz    (files to install)
    """
    with tempfile.TemporaryDirectory(prefix="deb_build_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1. Create control.tar.gz
        debian_dir = stage_dir / "DEBIAN"
        control_tar_path = tmp_path / "control.tar.gz"
        create_tar_archive(debian_dir, control_tar_path, prefix=".")

        # 2. Create data.tar.gz (excluding DEBIAN metadata directory)
        data_stage = tmp_path / "data_stage"
        data_stage.mkdir()
        for item in stage_dir.iterdir():
            if item.name != "DEBIAN":
                if item.is_dir():
                    copy_tree_filtered(item, data_stage / item.name)
                else:
                    shutil.copy2(item, data_stage / item.name)

        data_tar_path = tmp_path / "data.tar.gz"
        create_tar_archive(data_stage, data_tar_path, prefix=".")

        # 3. Assemble Unix AR archive
        def make_ar_header(name: str, size: int, mtime: int = 1700000000, mode: int = 0o100644) -> bytes:
            name_bytes = f"{name:<16}".encode("ascii")[:16]
            mtime_bytes = f"{mtime:<12}".encode("ascii")[:12]
            uid_bytes = b"0     "
            gid_bytes = b"0     "
            mode_bytes = f"{oct(mode)[2:]:>6}  ".encode("ascii")[:8]
            size_bytes = f"{size:<10}".encode("ascii")[:10]
            trailer = b"\x60\x0a"
            return name_bytes + mtime_bytes + uid_bytes + gid_bytes + mode_bytes + size_bytes + trailer

        deb_output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(deb_output_path, "wb") as deb:
            # Global AR magic
            deb.write(b"!<arch>\n")

            # Member 1: debian-binary
            deb_bin = b"2.0\n"
            deb.write(make_ar_header("debian-binary", len(deb_bin)))
            deb.write(deb_bin)
            if len(deb_bin) % 2 != 0:
                deb.write(b"\n")

            # Member 2: control.tar.gz
            ctrl_bytes = control_tar_path.read_bytes()
            deb.write(make_ar_header("control.tar.gz", len(ctrl_bytes)))
            deb.write(ctrl_bytes)
            if len(ctrl_bytes) % 2 != 0:
                deb.write(b"\n")

            # Member 3: data.tar.gz
            data_bytes = data_tar_path.read_bytes()
            deb.write(make_ar_header("data.tar.gz", len(data_bytes)))
            deb.write(data_bytes)
            if len(data_bytes) % 2 != 0:
                deb.write(b"\n")


def build_deb(
    version: str | None = None,
    release: str = "1",
    arch: str = "all",
    output_dir: str = "dist",
    force_internal: bool = False,
    keep_stage: bool = False,
) -> Path:
    """Build Debian / Ubuntu .deb package."""
    project_root = get_project_root()
    meta = load_project_metadata(project_root)
    pkg_ver = version or meta["version"]
    pkg_name = meta["name"]
    full_ver = f"{pkg_ver}-{release}"
    deb_filename = f"{pkg_name}_{full_ver}_{arch}.deb"

    out_dir = project_root / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    deb_path = out_dir / deb_filename

    print(f"==> Building Debian package: {deb_filename}")
    print(f"    Version:      {full_ver}")
    print(f"    Architecture: {arch}")
    print(f"    Source root:  {project_root}")

    stage_parent = tempfile.mkdtemp(prefix="deb_stage_")
    stage_dir = Path(stage_parent) / "stage"
    stage_dir.mkdir()

    try:
        # 1. Target Directories
        app_share_dir = stage_dir / "usr" / "share" / "info-weather"
        bin_dir = stage_dir / "usr" / "bin"
        apps_dir = stage_dir / "usr" / "share" / "applications"
        icons_dir = stage_dir / "usr" / "share" / "icons" / "hicolor" / "scalable" / "apps"
        doc_dir = stage_dir / "usr" / "share" / "doc" / "info-weather"
        debian_dir = stage_dir / "DEBIAN"

        for d in (app_share_dir, bin_dir, apps_dir, icons_dir, doc_dir, debian_dir):
            d.mkdir(parents=True, exist_ok=True)

        # 2. Copy Application Files into /usr/share/info-weather
        print("    [+] Copying application modules and assets...")
        shutil.copy2(project_root / "main.py", app_share_dir / "main.py")

        for mod in ("core", "models", "providers", "data", "ui", "assets"):
            src_mod = project_root / mod
            if src_mod.is_dir():
                copy_tree_filtered(src_mod, app_share_dir / mod)

        # Copy KDE window rules
        kde_rule_dir = app_share_dir / "packaging" / "kde"
        kde_rule_dir.mkdir(parents=True, exist_ok=True)
        for f in ("info-weather.kwinrule", "install_kwinrule.sh"):
            p = project_root / "packaging" / "kde" / f
            if p.is_file():
                shutil.copy2(p, kde_rule_dir / f)

        for doc_file in ("NOTICE", "README.md", "LICENSE"):
            p = project_root / doc_file
            if p.is_file():
                shutil.copy2(p, app_share_dir / doc_file)

        # 3. Create /usr/bin/info-weather executable launcher
        launcher_path = bin_dir / "info-weather"
        launcher_content = (
            "#!/bin/sh\n"
            "# info-weather desktop widget launcher\n"
            "exec python3 /usr/share/info-weather/main.py \"$@\"\n"
        )
        launcher_path.write_text(launcher_content, encoding="utf-8")
        launcher_path.chmod(0o755)

        # 4. Desktop entry and Icon
        desktop_src = project_root / "packaging" / "info-weather.desktop"
        desktop_dst = apps_dir / "info-weather.desktop"
        if desktop_src.is_file():
            desktop_content = desktop_src.read_text(encoding="utf-8")
            # Ensure Icon points to info-weather
            desktop_content = re.sub(r"^Icon=.*", "Icon=info-weather", desktop_content, flags=re.MULTILINE)
            desktop_dst.write_text(desktop_content, encoding="utf-8")
        else:
            desktop_dst.write_text(
                "[Desktop Entry]\n"
                "Name=Info Weather\n"
                "Comment=Modern Linux desktop weather widget\n"
                "Exec=info-weather\n"
                "TryExec=info-weather\n"
                "Icon=info-weather\n"
                "Terminal=false\n"
                "Type=Application\n"
                "Categories=Utility;Clock;Qt;\n"
                "StartupWMClass=info-weather\n"
                "Keywords=weather;forecast;meteo;widget;plasma;\n",
                encoding="utf-8"
            )

        # 4b. AppStream metadata
        metainfo_dir = stage_dir / "usr" / "share" / "metainfo"
        metainfo_dir.mkdir(parents=True, exist_ok=True)
        metainfo_src = project_root / "packaging" / "io.github.aimakosi.info_weather.metainfo.xml"
        if metainfo_src.is_file():
            shutil.copy2(metainfo_src, metainfo_dir / metainfo_src.name)

        icon_src = project_root / "assets" / "icons" / "info-weather.svg"
        if icon_src.is_file():
            shutil.copy2(icon_src, icons_dir / "info-weather.svg")

        # 5. Documentation and copyright
        notice_src = project_root / "NOTICE"
        copyright_dst = doc_dir / "copyright"
        if notice_src.is_file():
            shutil.copy2(notice_src, copyright_dst)
        else:
            copyright_dst.write_text(f"License: {meta['license']}\n", encoding="utf-8")

        readme_src = project_root / "README.md"
        if readme_src.is_file():
            shutil.copy2(readme_src, doc_dir / "README.md")

        # 6. Calculate installed size (in KB) and md5sums
        print("    [+] Calculating package size and md5sums...")
        total_bytes = 0
        md5_lines = []
        for root, _, files in os.walk(stage_dir / "usr"):
            for f in files:
                fp = Path(root) / f
                total_bytes += fp.stat().st_size
                rel = fp.relative_to(stage_dir).as_posix()
                md5_lines.append(f"{calculate_md5(fp)}  {rel}")

        installed_size_kb = max(1, total_bytes // 1024)
        (debian_dir / "md5sums").write_text("\n".join(md5_lines) + "\n", encoding="utf-8")

        # 7. Generate DEBIAN/control
        control_content = (
            f"Package: {pkg_name}\n"
            f"Version: {full_ver}\n"
            f"Section: x11\n"
            f"Priority: optional\n"
            f"Architecture: {arch}\n"
            f"Depends: python3 (>= 3.10), python3-pyside6.qtwidgets, python3-pyside6.qtsvg, python3-pil\n"
            f"Recommends: kwin-common | kwin-x11 | kwin-wayland\n"
            f"Suggests: qdbus-qt5 | qdbus-qt6\n"
            f"Maintainer: {meta['maintainer']}\n"
            f"Installed-Size: {installed_size_kb}\n"
            f"Homepage: {meta['homepage']}\n"
            f"Description: {meta['description']}\n"
            f" info-weather is a modern, lightweight, frameless desktop weather widget\n"
            f" for Linux desktop environments (KDE Plasma, GNOME, XFCE).\n"
            f" Features multi-source weather consensus (Open-Meteo, MET Norway, wttr.in),\n"
            f" built-in ERA5 climatology offline fallback, 3-screen detailed forecast,\n"
            f" full 16-point wind rose, live weather effects, and rich skin support.\n"
        )
        (debian_dir / "control").write_text(control_content, encoding="utf-8")

        # 8. Generate DEBIAN/postinst & postrm
        postinst_content = (
            "#!/bin/sh\n"
            "set -e\n"
            "if [ \"$1\" = \"configure\" ]; then\n"
            "    if command -v update-desktop-database >/dev/null 2>&1; then\n"
            "        update-desktop-database -q /usr/share/applications || true\n"
            "    fi\n"
            "    if command -v gtk-update-icon-cache >/dev/null 2>&1; then\n"
            "        gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true\n"
            "    fi\n"
            "fi\n"
            "exit 0\n"
        )
        postinst_file = debian_dir / "postinst"
        postinst_file.write_text(postinst_content, encoding="utf-8")
        postinst_file.chmod(0o755)

        postrm_content = (
            "#!/bin/sh\n"
            "set -e\n"
            "if [ \"$1\" = \"remove\" ] || [ \"$1\" = \"purge\" ]; then\n"
            "    if command -v update-desktop-database >/dev/null 2>&1; then\n"
            "        update-desktop-database -q /usr/share/applications || true\n"
            "    fi\n"
            "    if command -v gtk-update-icon-cache >/dev/null 2>&1; then\n"
            "        gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true\n"
            "    fi\n"
            "fi\n"
            "exit 0\n"
        )
        postrm_file = debian_dir / "postrm"
        postrm_file.write_text(postrm_content, encoding="utf-8")
        postrm_file.chmod(0o755)

        # 9. Build .deb
        dpkg_deb = shutil.which("dpkg-deb")
        if dpkg_deb and not force_internal:
            print(f"    [+] Packing using system {dpkg_deb}...")
            cmd = [dpkg_deb, "--build", "--root-owner-group", str(stage_dir), str(deb_path)]
            subprocess.run(cmd, check=True)
        else:
            print("    [+] Packing using internal pure-Python AR/tar engine...")
            build_deb_pure_python(stage_dir, deb_path)

        # 10. Summary
        deb_size_kb = deb_path.stat().st_size / 1024.0
        deb_sha256 = calculate_sha256(deb_path)

        print("")
        print("==> Debian package built successfully!")
        print(f"    File:   {deb_path}")
        print(f"    Size:   {deb_size_kb:.1f} KB ({deb_path.stat().st_size} bytes)")
        print(f"    SHA256: {deb_sha256}")
        print("")
        print("To install on Ubuntu/Debian:")
        print(f"    sudo apt install ./{deb_path.name}")
        print("    or:")
        print(f"    sudo dpkg -i {deb_path.name} && sudo apt-get install -f")

        return deb_path

    finally:
        if not keep_stage:
            shutil.rmtree(stage_parent, ignore_errors=True)
        else:
            print(f"    [i] Staging directory preserved at: {stage_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Debian/Ubuntu (.deb) package for info-weather.")
    parser.add_argument("--version", "-v", help="Override package version (default: from pyproject.toml)")
    parser.add_argument("--release", "-r", default="1", help="Debian package release revision (default: 1)")
    parser.add_argument("--arch", "-a", default="all", help="Target architecture (default: all)")
    parser.add_argument("--output-dir", "-o", default="dist", help="Output directory for .deb file (default: dist)")
    parser.add_argument("--internal-only", action="store_true", help="Force internal Python AR builder even if dpkg-deb exists")
    parser.add_argument("--keep-stage", action="store_true", help="Keep temporary staging directory for inspection")

    args = parser.parse_args()

    try:
        build_deb(
            version=args.version,
            release=args.release,
            arch=args.arch,
            output_dir=args.output_dir,
            force_internal=args.internal_only,
            keep_stage=args.keep_stage,
        )
        return 0
    except Exception as e:
        print(f"ERROR: Failed to build Debian package: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
