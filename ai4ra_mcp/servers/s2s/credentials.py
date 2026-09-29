"""The person's S2S credential: a client certificate and its private key, and optionally the CA
that signs the endpoint's server certificate. It travels as the bearer token, base64url of a
JSON object {"cert": PEM, "key": PEM, "ca": PEM?}, so it never appears in a tool argument or a
model's context; `python -m ai4ra_mcp.servers.s2s.credentials cert.pem key.pem [ca.pem]` prints
one. A deployment may hold a fallback pair in files for clients that cannot send a bearer."""

from __future__ import annotations

import base64
import json
import os
import ssl
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import ec, rsa

CERT_FILE_ENV = "AI4RA_MCP_S2S_CERT_FILE"
KEY_FILE_ENV = "AI4RA_MCP_S2S_KEY_FILE"
CA_FILE_ENV = "AI4RA_MCP_S2S_CA_FILE"


@dataclass(frozen=True)
class Bundle:
    cert: str
    key: str
    ca: str | None = None
    source: str = "bearer"

    def ssl_context(self, ca_file: str | None = None) -> ssl.SSLContext:
        """A client context presenting this certificate. The server is verified against the bundle's
        CA, else `ca_file`, else the system trust store. Key material touches disk only in a private
        temp dir for the milliseconds load_cert_chain needs it."""
        ctx = ssl.create_default_context()
        if self.ca:
            ctx.load_verify_locations(cadata=self.ca)
        elif ca_file:
            ctx.load_verify_locations(cafile=ca_file)
        with tempfile.TemporaryDirectory() as d:
            c, k = Path(d) / "c.pem", Path(d) / "k.pem"
            c.write_text(self.cert)
            k.write_text(self.key)
            os.chmod(k, 0o600)
            ctx.load_cert_chain(str(c), str(k))
        return ctx


def _pem(s: str, kind: str) -> str:
    s = (s or "").strip()
    if "-----BEGIN" not in s:
        raise ValueError(f"the {kind} in the credential is not PEM text")
    return s + "\n"


def from_token(token: str | None) -> Bundle | None:
    """The bundle a bearer token carries, or None when there is no token. A token that is not a bundle raises."""
    if not token:
        return None
    raw = token.strip()
    if not raw.startswith("{"):
        try:
            raw = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode()
        except Exception as exc:  # noqa: BLE001
            raise ValueError("the bearer token is not a base64url-encoded S2S credential bundle") from exc
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("the bearer token decodes but is not JSON") from exc
    if not isinstance(obj, dict) or "cert" not in obj or "key" not in obj:
        raise ValueError('the credential bundle needs "cert" and "key" (PEM), optionally "ca"')
    return Bundle(_pem(obj["cert"], "cert"), _pem(obj["key"], "key"), _pem(obj["ca"], "ca") if obj.get("ca") else None)


def from_env() -> Bundle | None:
    c, k = os.environ.get(CERT_FILE_ENV, "").strip(), os.environ.get(KEY_FILE_ENV, "").strip()
    if not (c and k):
        return None
    try:
        return Bundle(Path(c).read_text(), Path(k).read_text(), None, source="environment")
    except OSError as exc:
        raise ValueError(f"the deployment's fallback certificate could not be read: {exc}") from exc


def _dn(name: x509.Name) -> dict:
    """A distinguished name as {attribute: value}, keyed the way OpenSSL prints it (C, ST, L, O, OU, CN)."""
    short = {"countryName": "C", "stateOrProvinceName": "ST", "localityName": "L", "organizationName": "O", "organizationalUnitName": "OU", "commonName": "CN"}
    return {short.get(a.oid._name, a.oid._name): str(a.value) for a in name}


def describe(cert_pem: str) -> dict:
    """What Grants.gov and eRA support ask for when a certificate misbehaves: subject, issuer, serial,
    validity, key, signature algorithm, and whether the Client Authentication EKU is present (some CAs
    have dropped it; Grants.gov does not require it, a vendor's stack might)."""
    cert = x509.load_pem_x509_certificate(cert_pem.encode())
    now = datetime.now(timezone.utc)
    nb, na = cert.not_valid_before_utc, cert.not_valid_after_utc
    key = cert.public_key()
    if isinstance(key, rsa.RSAPublicKey):
        key_desc = f"RSA {key.key_size}"
    elif isinstance(key, ec.EllipticCurvePublicKey):
        key_desc = f"EC {key.curve.name}"
    else:
        key_desc = type(key).__name__
    try:
        eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        client_auth = x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH in eku
    except x509.ExtensionNotFound:
        client_auth = None
    try:
        sans = [str(n.value) for n in cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value]
    except x509.ExtensionNotFound:
        sans = []
    return {
        "subject": _dn(cert.subject), "issuer": _dn(cert.issuer), "serial_hex": format(cert.serial_number, "x").upper(),
        "not_before": nb.isoformat(), "not_after": na.isoformat(), "days_left": (na - now).days, "expired": na < now, "not_yet_valid": nb > now,
        "key": key_desc, "signature_algorithm": cert.signature_algorithm_oid._name, "version": cert.version.name,
        "client_auth_eku": client_auth, "subject_alt_names": sans,
        "meets_grants_gov_minimums": isinstance(key, rsa.RSAPublicKey) and key.key_size >= 2048 and "sha1" not in cert.signature_algorithm_oid._name.lower() and cert.version.name == "v3",
    }


def make_token(cert_path: str, key_path: str, ca_path: str | None = None) -> str:
    obj = {"cert": Path(cert_path).read_text(), "key": Path(key_path).read_text()}
    if ca_path:
        obj["ca"] = Path(ca_path).read_text()
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        sys.exit("usage: python -m ai4ra_mcp.servers.s2s.credentials cert.pem key.pem [ca.pem]  -> prints the bearer token")
    print(make_token(*sys.argv[1:]))
