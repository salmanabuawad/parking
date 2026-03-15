"""
Digital signing for blurred/processed videos.

Each processed video gets an RSA-PSS signature over a manifest that includes:
  - SHA-256 hash of the video bytes
  - job_id, ticket_id, captured_at, system tag

The private key is generated once and stored on disk alongside the videos.
The public key (PEM) is stored separately and can be distributed for verification.

Usage:
    signer = VideoSigner(keys_dir)
    sig_hex, pubkey_pem = signer.sign(video_bytes, manifest_meta)
    ok = VideoSigner.verify(video_bytes, manifest_meta, sig_hex, pubkey_pem)
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.backends import default_backend
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False


SYSTEM_TAG = "parking-enforcement-v1"


class VideoSigner:
    """Manages RSA key pair and signs video manifests."""

    def __init__(self, keys_dir: str | Path) -> None:
        if not _CRYPTO_AVAILABLE:
            raise RuntimeError(
                "cryptography package is required for video signing. "
                "Install with: pip install cryptography"
            )
        self._keys_dir = Path(keys_dir)
        self._keys_dir.mkdir(parents=True, exist_ok=True)
        self._priv_path = self._keys_dir / "signing_key.pem"
        self._pub_path  = self._keys_dir / "signing_public_key.pem"
        self._private_key = self._load_or_generate_key()

    # ------------------------------------------------------------------
    # Key management
    # ------------------------------------------------------------------

    def _load_or_generate_key(self):
        if self._priv_path.exists():
            pem = self._priv_path.read_bytes()
            return serialization.load_pem_private_key(pem, password=None, backend=default_backend())
        # Generate 2048-bit RSA key
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )
        priv_pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub_pem = key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self._priv_path.write_bytes(priv_pem)
        self._pub_path.write_bytes(pub_pem)
        return key

    def public_key_pem(self) -> str:
        return self._pub_path.read_text()

    def public_key_fingerprint(self) -> str:
        """SHA-256 fingerprint of the public key DER bytes (hex, first 16 chars)."""
        pub_der = self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return hashlib.sha256(pub_der).hexdigest()[:16]

    # ------------------------------------------------------------------
    # Signing
    # ------------------------------------------------------------------

    @staticmethod
    def _build_manifest(video_bytes: bytes, meta: dict[str, Any]) -> bytes:
        video_sha256 = hashlib.sha256(video_bytes).hexdigest()
        manifest = {
            "system":      SYSTEM_TAG,
            "video_sha256": video_sha256,
            **{k: str(v) if v is not None else None for k, v in meta.items()},
        }
        return json.dumps(manifest, sort_keys=True, ensure_ascii=True).encode("utf-8")

    def sign(self, video_bytes: bytes, meta: dict[str, Any]) -> tuple[str, str]:
        """Sign the video + metadata.

        Returns:
            (signature_hex, public_key_pem)
        """
        manifest = self._build_manifest(video_bytes, meta)
        sig = self._private_key.sign(
            manifest,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return sig.hex(), self.public_key_pem()

    # ------------------------------------------------------------------
    # Verification (static — only needs the public key)
    # ------------------------------------------------------------------

    @staticmethod
    def verify(video_bytes: bytes, meta: dict[str, Any], sig_hex: str, public_key_pem: str) -> bool:
        """Verify a previously created signature. Returns True if valid."""
        if not _CRYPTO_AVAILABLE:
            raise RuntimeError("cryptography package not installed")
        try:
            from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
            from cryptography.exceptions import InvalidSignature

            pub = serialization.load_pem_public_key(
                public_key_pem.encode("utf-8") if isinstance(public_key_pem, str) else public_key_pem,
                backend=default_backend(),
            )
            manifest = VideoSigner._build_manifest(video_bytes, meta)
            pub.verify(
                bytes.fromhex(sig_hex),
                manifest,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
            return True
        except Exception:
            return False


def sign_processed_video(
    video_bytes: bytes,
    job_id: int,
    ticket_id: int,
    captured_at: datetime | None,
    keys_dir: str | Path,
) -> tuple[str, str, str]:
    """Convenience wrapper used by the upload worker.

    Returns:
        (signature_hex, public_key_pem, key_fingerprint)
    """
    signer = VideoSigner(keys_dir)
    meta = {
        "job_id":      job_id,
        "ticket_id":   ticket_id,
        "captured_at": captured_at.isoformat() if captured_at else None,
    }
    sig_hex, pubkey_pem = signer.sign(video_bytes, meta)
    fingerprint = signer.public_key_fingerprint()
    return sig_hex, pubkey_pem, fingerprint
