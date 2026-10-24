#!/usr/bin/env python3
"""
Arch Linux Package and PKGBUILD Builder for info-weather.

Generates:
  1. Standard Arch Linux PKGBUILD, .SRCINFO, and install script in packaging/arch/
  2. Release source tarball (info-weather-<ver>.tar.gz) with computed SHA256
  3. Binary pacman package (.pkg.tar.zst / .pkg.tar.xz) ready to install via `pacman -U`

Usage:
    python packaging/scripts/build_pkg.py
    python packaging/scripts/build_pkg.py --version 0.1.0 --release 1 --output-dir dist/
    python packaging/scripts/build_pkg.py --source-only   # Generate only PKGBUILD + source tarball for AUR
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
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


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def create_source_tarball(project_root: Path, out_tar_path: Path, pkg_name: str, pkg_ver: str) -> str:
    """Create a clean source release tarball (.tar.gz) for PKGBUILD/AUR."""
    prefix = f"{pkg_name}-{pkg_ver}"
    out_tar_path.parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(out_tar_path, "w:gz", format=tarfile.PAX_FORMAT) as tar:
        # 1. Root files
        for f in ("main.py", "pyproject.toml", "README.md", "NOTICE", "LICENSE"):
            fp = project_root / f
            if fp.is_file():
                ti = tar.gettarinfo(str(fp), arcname=f"{prefix}/{f}")
                ti.uid, ti.gid = 0, 0
                ti.uname, ti.gname = "root", "root"
                ti.mtime = 1700000000
                ti.mode = 0o755 if f == "main.py" else 0o644
                with open(fp, "rb") as sfp:
                    tar.addfile(ti, sfp)

        # 2. Modules and directories
        for d in ("core", "models", "providers", "data", "ui", "assets", "packaging"):
            src_dir = project_root / d
            if src_dir.is_dir():
                for root, dirs, files in os.walk(src_dir):
                    dirs[:] = [sub for sub in dirs if sub not in ("__pycache__", ".pytest_cache", ".git", "arch")]
                    dirs.sort()
                    files.sort()
                    rel_dir = Path(root).relative_to(project_root)

                    tar_dir_name = f"{prefix}/{rel_dir.as_posix()}"
                    ti = tar.gettarinfo(root, arcname=tar_dir_name)
                    ti.uid, ti.gid = 0, 0
                    ti.uname, ti.gname = "root", "root"
                    ti.mtime = 1700000000
                    ti.mode = 0o755
                    tar.addfile(ti)

                    for f in files:
                        if f.endswith((".pyc", ".pyo", ".swp", ".bak", ".tmp", "~")) or f == "Thumbs.db":
                            continue
                        fp = Path(root) / f
                        rel_file = fp.relative_to(project_root)
                        tar_file_name = f"{prefix}/{rel_file.as_posix()}"

                        ti = tar.gettarinfo(str(fp), arcname=tar_file_name)
                        ti.uid, ti.gid = 0, 0
                        ti.uname, ti.gname = "root", "root"
                        ti.mtime = 1700000000
                        ti.mode = 0o755 if f.endswith(".sh") or f == "main.py" else 0o644
                        with open(fp, "rb") as sfp:
                            tar.addfile(ti, sfp)

    return calculate_sha256(out_tar_path)


def generate_pkgbuild(
    arch_dir: Path,
    meta: dict[str, str],
    version: str,
    release: str,
    source_tar_name: str,
    sha256: str,
) -> None:
    """Generate PKGBUILD, .SRCINFO, and install script."""
    arch_dir.mkdir(parents=True, exist_ok=True)
    pkg_name = meta["name"]

    # 1. info-weather.install
    install_script = (
        "post_install() {\n"
        "    update-desktop-database -q 2>/dev/null || true\n"
        "    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor 2>/dev/null || true\n"
        "}\n\n"
        "post_upgrade() {\n"
        "    post_install\n"
        "}\n\n"
        "post_remove() {\n"
        "    post_install\n"
        "}\n"
    )
    (arch_dir / f"{pkg_name}.install").write_text(install_script, encoding="utf-8")

    # 2. PKGBUILD
    pkgbuild_content = (
        f"# Maintainer: {meta['maintainer']}\n"
        f"pkgname={pkg_name}\n"
        f"pkgver={version}\n"
        f"pkgrel={release}\n"
        f"pkgdesc=\"{meta['description']}\"\n"
        f"arch=('any')\n"
        f"url=\"{meta['homepage']}\"\n"
        f"license=('GPL-3.0-or-later')\n"
        f"depends=('python>=3.10' 'pyside6' 'python-pillow')\n"
        f"optdepends=(\n"
        f"    'kwin: for desktop pinning rules on KDE Plasma'\n"
        f"    'qt5-tools: for qdbus rule reconfigure in KDE Plasma 5'\n"
        f"    'qt6-tools: for qdbus6 rule reconfigure in KDE Plasma 6'\n"
        f")\n"
        f"install=\"{pkg_name}.install\"\n"
        f"source=(\"{source_tar_name}\")\n"
        f"sha256sums=('{sha256}')\n\n"
        f"package() {{\n"
        f"    cd \"$srcdir/${{pkgname}}-${{pkgver}}\"\n\n"
        f"    # 1. Install application modules and assets\n"
        f"    install -dm755 \"$pkgdir/usr/share/{pkg_name}\"\n"
        f"    cp -r core models providers data ui assets main.py NOTICE README.md \"$pkgdir/usr/share/{pkg_name}/\"\n"
        f"    find \"$pkgdir/usr/share/{pkg_name}\" -type d -exec chmod 755 {{}} +\n"
        f"    find \"$pkgdir/usr/share/{pkg_name}\" -type f -exec chmod 644 {{}} +\n"
        f"    chmod 755 \"$pkgdir/usr/share/{pkg_name}/main.py\"\n\n"
        f"    # 2. Install KDE window rule helper\n"
        f"    install -dm755 \"$pkgdir/usr/share/{pkg_name}/packaging/kde\"\n"
        f"    install -m644 packaging/kde/info-weather.kwinrule \"$pkgdir/usr/share/{pkg_name}/packaging/kde/\"\n"
        f"    install -m755 packaging/kde/install_kwinrule.sh \"$pkgdir/usr/share/{pkg_name}/packaging/kde/\"\n\n"
        f"    # 3. Create executable launcher in /usr/bin\n"
        f"    install -dm755 \"$pkgdir/usr/bin\"\n"
        f"    cat << 'EOF' > \"$pkgdir/usr/bin/{pkg_name}\"\n"
        f"#!/bin/sh\n"
        f"exec python3 /usr/share/{pkg_name}/main.py \"$@\"\n"
        f"EOF\n"
        f"    chmod 755 \"$pkgdir/usr/bin/{pkg_name}\"\n\n"
        f"    # 4. Install desktop entry\n"
        f"    install -Dm644 packaging/info-weather.desktop \"$pkgdir/usr/share/applications/info-weather.desktop\"\n\n"
        f"    # 4b. Install AppStream metadata\n"
        f"    install -Dm644 packaging/io.github.aimakosi.info_weather.metainfo.xml \"$pkgdir/usr/share/metainfo/io.github.aimakosi.info_weather.metainfo.xml\"\n\n"
        f"    # 5. Install application icon\n"
        f"    install -Dm644 assets/icons/info-weather.svg \"$pkgdir/usr/share/icons/hicolor/scalable/apps/info-weather.svg\"\n\n"
        f"    # 6. Install documentation & license\n"
        f"    install -Dm644 NOTICE \"$pkgdir/usr/share/licenses/{pkg_name}/NOTICE\"\n"
        f"    install -Dm644 LICENSE \"$pkgdir/usr/share/licenses/{pkg_name}/LICENSE\"\n"
        f"    install -Dm644 README.md \"$pkgdir/usr/share/doc/{pkg_name}/README.md\"\n"
        f"}}\n"
    )
    (arch_dir / "PKGBUILD").write_text(pkgbuild_content, encoding="utf-8")

    # 3. .SRCINFO (standard AUR metadata)
    srcinfo_content = (
        f"pkgbase = {pkg_name}\n"
        f"\tpkgdesc = {meta['description']}\n"
        f"\tpkgver = {version}\n"
        f"\tpkgrel = {release}\n"
        f"\turl = {meta['homepage']}\n"
        f"\tinstall = {pkg_name}.install\n"
        f"\tarch = any\n"
        f"\tlicense = GPL-3.0-or-later\n"
        f"\tdepends = python>=3.10\n"
        f"\tdepends = pyside6\n"
        f"\tdepends = python-pillow\n"
        f"\toptdepends = kwin: for desktop pinning rules on KDE Plasma\n"
        f"\toptdepends = qt5-tools: for qdbus rule reconfigure in KDE Plasma 5\n"
        f"\toptdepends = qt6-tools: for qdbus6 rule reconfigure in KDE Plasma 6\n"
        f"\tsource = {source_tar_name}\n"
        f"\tsha256sums = {sha256}\n\n"
        f"pkgname = {pkg_name}\n"
    )
    (arch_dir / ".SRCINFO").write_text(srcinfo_content, encoding="utf-8")


def build_pkg(
    version: str | None = None,
    release: str = "1",
    output_dir: str = "dist",
    arch_dir: str = "packaging/arch",
    use_makepkg: bool = False,
) -> tuple[Path, Path | None]:
    """Generate Arch source assets (tarball, PKGBUILD, .SRCINFO) and optionally
    build the binary package with system makepkg."""
    project_root = get_project_root()
    meta = load_project_metadata(project_root)
    pkg_ver = version or meta["version"]
    pkg_name = meta["name"]

    out_dir = project_root / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    arch_packaging_dir = project_root / arch_dir
    arch_packaging_dir.mkdir(parents=True, exist_ok=True)

    src_tar_name = f"{pkg_name}-{pkg_ver}.tar.gz"
    src_tar_path = out_dir / src_tar_name

    print(f"==> Building Arch Linux package assets for {pkg_name} {pkg_ver}-{release}")

    # 1. Create source tarball
    print(f"    [+] Creating source release archive: {src_tar_name}...")
    sha256 = create_source_tarball(project_root, src_tar_path, pkg_name, pkg_ver)
    print(f"        SHA256: {sha256}")

    # Also copy source tarball to packaging/arch directory so makepkg works directly there
    shutil.copy2(src_tar_path, arch_packaging_dir / src_tar_name)

    # 2. Generate PKGBUILD, .SRCINFO, info-weather.install
    print("    [+] Generating PKGBUILD, .SRCINFO and install script in packaging/arch/...")
    generate_pkgbuild(arch_packaging_dir, meta, pkg_ver, release, src_tar_name, sha256)

    binary_pkg_path: Path | None = None

    makepkg_tool = shutil.which("makepkg")
    if use_makepkg and makepkg_tool:
        print(f"    [+] Building binary package using system makepkg ({makepkg_tool})...")
        cmd = [makepkg_tool, "-f", "--nodeps", "--noconfirm"]
        subprocess.run(cmd, cwd=arch_packaging_dir, check=True)
        for f in arch_packaging_dir.glob("*.pkg.tar.*"):
            dst = out_dir / f.name
            shutil.copy2(f, dst)
            binary_pkg_path = dst
            break
    elif use_makepkg:
        print("    [!] makepkg не найден — бинарный пакет собирается на Arch:")
        print(f"        cd {arch_dir} && makepkg -si")
    else:
        print("    [*] Бинарный пакет не собирается (нет --makepkg).")
        print(f"        Для сборки на Arch: cd {arch_dir} && makepkg -si")

    print("")
    print("==> Arch Linux packaging completed!")
    print(f"    Source archive: {src_tar_path} ({src_tar_path.stat().st_size / 1024.0:.1f} KB)")
    print(f"    PKGBUILD:       {arch_packaging_dir / 'PKGBUILD'}")
    print(f"    .SRCINFO:       {arch_packaging_dir / '.SRCINFO'}")

    if binary_pkg_path and binary_pkg_path.is_file():
        pkg_size_kb = binary_pkg_path.stat().st_size / 1024.0
        pkg_sha256 = calculate_sha256(binary_pkg_path)
        print(f"    Binary package: {binary_pkg_path} ({pkg_size_kb:.1f} KB)")
        print(f"    SHA256:         {pkg_sha256}")
        print("")
        print("To install on Arch Linux / Manjaro / EndeavourOS:")
        print(f"    sudo pacman -U {binary_pkg_path.name}")
        print("")
        print("To build via makepkg:")
        print(f"    cd {arch_dir} && makepkg -si")

    return src_tar_path, binary_pkg_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Arch Linux (PKGBUILD / pacman) package for info-weather.")
    parser.add_argument("--version", "-v", help="Override package version (default: from pyproject.toml)")
    parser.add_argument("--release", "-r", default="1", help="Package release revision (default: 1)")
    parser.add_argument("--output-dir", "-o", default="dist", help="Output directory for generated packages (default: dist)")
    parser.add_argument("--arch-dir", default="packaging/arch", help="Directory for PKGBUILD and .SRCINFO (default: packaging/arch)")
    parser.add_argument("--makepkg", action="store_true", help="Build the binary package with system makepkg (Arch)")

    args = parser.parse_args()

    try:
        build_pkg(
            version=args.version,
            release=args.release,
            output_dir=args.output_dir,
            arch_dir=args.arch_dir,
            use_makepkg=args.makepkg,
        )
        return 0
    except Exception as e:
        print(f"ERROR: Failed to build Arch Linux package: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
