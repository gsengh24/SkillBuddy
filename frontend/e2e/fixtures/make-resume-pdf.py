"""Writes synthetic-resume.pdf: a one-page resume for a person who does not exist.

Synthetic data only (CLAUDE.md): the name, email, phone and address are made up. Standard
library only; run `python3 make-resume-pdf.py` in this folder to rebuild the file.
"""

from pathlib import Path

LINES = [
    "Aarav Example",
    "aarav.example@example.com  |  +91 90000 12345  |  linkedin.com/in/aarav-example",
    "Address: 1 Sample Road, Patiala 147001",
    "",
    "Second-year CSE student. I build mobile and web apps with Flutter and React,",
    "and design my own screens in Figma (UI design). Firebase for the backend.",
    "Shipped a campus events app used by two societies, 2024 - 2025.",
    "Public speaking: led three workshops.",
    "",
    "Interests: Hackathons, ML tracks, chess and street photography.",
]


def escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build() -> bytes:
    stream = ["BT", "/F1 11 Tf", "14 TL", "56 780 Td"]
    for line in LINES:
        stream.append(f"({escape(line)}) Tj T*")
    stream.append("ET")
    content = "\n".join(stream).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


if __name__ == "__main__":
    Path(__file__).with_name("synthetic-resume.pdf").write_bytes(build())
