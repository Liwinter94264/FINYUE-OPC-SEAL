# Third-party notices — FINYUE · OPC盖章 1.0.0

Application code: GNU AGPL version 3 only. Publisher: 凛野（北京）文化传媒有限公司. Original upstream authors retain their component copyrights. No Artifex commercial license is claimed.

| Component | Version | License and notice |
| --- | --- | --- |
| PyMuPDF / MuPDF | 1.28.2 / bundled native source version | AGPL v3 or Artifex commercial; this release uses AGPL. See LICENSE, licenses/PyMuPDF-COPYING and bundled MuPDF notices |
| Pillow | 12.3.0 | MIT-CMU and bundled native component notices: licenses/Pillow-LICENSE |
| Python | 3.12.14 | PSF and included notices: licenses/Python-LICENSE.txt |
| Tcl / Tk | 8.6 | Tcl/Tk license and bundled notices in licenses/ |
| PyInstaller | 6.22.3 | GPL-2.0-or-later with distribution exception: licenses/pyinstaller-COPYING.txt |
| Community hooks | 2026.8 | GPL-2.0-or-later build hooks; Apache-2.0 runtime hooks: licenses/pyinstaller-hooks-contrib-LICENSE |
| altgraph | 0.17.5 | MIT: licenses/altgraph-LICENSE |
| packaging | 26.3 | Apache-2.0 or BSD-2-Clause: licenses/packaging-LICENSE* |
| pefile | 2024.8.26 | MIT: licenses/pefile-LICENSE |
| pywin32-ctypes | 0.2.3 | BSD-3-Clause: licenses/pywin32-ctypes-LICENSE.txt |
| setuptools | 84.0.0 | MIT and bundled notices: licenses/setuptools-LICENSE* |

The license directory contains unmodified installed distribution notices and bundled MuPDF notices. The application's offline legal reader displays these complete files. Windows Chinese fonts are used from the OS and are not redistributed.

The corresponding application source, build spec, dependency versions and manifest are alongside the executable at:
https://github.com/Liwinter94264/FINYUE-OPC-SEAL/releases/tag/v1.0.0

That same Release provides an upstream-source ZIP containing unmodified PyMuPDF, MuPDF 1.28.2 with native third-party sources, Pillow, its Windows native dependencies (including libavif codec inputs), PyInstaller and community hooks. Pillow native sources are taken from the upstream pillow-depends mirror at the exact commit recorded in the source URLs; the unmodified Pillow winbuild/build_prepare.py retains upstream build patches. UPSTREAM-SOURCES.json gives exact inputs and SHA256 values. The PyMuPDF native build entry and separate MuPDF source inputs are included; place the MuPDF archive beside setup.py as mupdf.tgz, or set PYMUPDF_SETUP_MUPDF_BUILD to its extracted directory as documented upstream. Upstream wheels and source distributions have not been patched by this application.

AGPL binary redistribution requires corresponding source and notices. Modified versions used to provide network interaction must offer users the modified corresponding source. Ordinary users need not publish the PDFs, seals or signatures they process. LICENSE is the controlling text. The PyInstaller distribution exception does not override application or library licenses.

The anonymous generated decoration has its prompt, origin and SHA256 in assets/auth-decoration-v1.source.json. It is licensed with the application to the extent such rights exist. Public packages omit official mascot/icon bitmaps, actual accounts, PDFs, seals, signatures, DPAPI data and local-defaults.json. Code permissions do not independently grant FINYUE trademark rights.
