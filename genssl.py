from cryptography import x509
from cryptography.x509.oid import NameOID
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pathlib import Path
from typing import Tuple
import uuid
import ipaddress


def generate_ca(p: Path, co, o, ou: str, size: int = 2048, valid: timedelta = timedelta(1, 0, 0)) -> Tuple[x509.Certificate, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(key_size=size, public_exponent=65537)
    
    # Create name object once and reuse
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, co),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, o),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, ou),
    ])
    
    now = datetime.today()
    builder = (x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .not_valid_before(now)
        .not_valid_after(now + valid)
        .serial_number(int(uuid.uuid4()))
        .public_key(key.public_key())
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=False, content_commitment=False,
                key_encipherment=False, data_encipherment=False,
                key_agreement=False, key_cert_sign=True,
                crl_sign=True, encipher_only=False,
                decipher_only=False
            ), critical=True)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
            critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()),
            critical=False))

    cert = builder.sign(private_key=key, algorithm=hashes.SHA256())
    
    # Use context managers for file operations
    _save_cert_and_key(p, cert, key)
    return cert, key


def generate_csr(p: Path, co, o, ou: str, size: int = 2048) -> Tuple[x509.CertificateSigningRequest, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(key_size=size, public_exponent=65537)
    
    csr = (x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, co),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, o),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, ou),
        ]))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(co),
                x509.IPAddress(ipaddress.IPv4Address('0.0.0.0'))  # Wildcard IP
            ]),
            critical=False)
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=True,
                key_encipherment=True, data_encipherment=True,
                key_agreement=False, key_cert_sign=False,
                crl_sign=False, encipher_only=False,
                decipher_only=False
            ), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([
                x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
                x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH
            ]), critical=True)
        .sign(key, hashes.SHA256()))
    
    # Save only the key since CSR is temporary
    _save_key(p, key)
    return csr, key


def generate_cert(p: Path, csr: x509.CertificateSigningRequest, cert: x509.Certificate, 
                 key: rsa.RSAPrivateKey, valid: timedelta = timedelta(1, 0, 0)) -> x509.Certificate:
    now = datetime.today()
    builder = (x509.CertificateBuilder()
        .issuer_name(cert.issuer)
        .subject_name(csr.subject)
        .public_key(csr.public_key())
        .not_valid_before(now)
        .not_valid_after(now + valid)
        .serial_number(int(uuid.uuid4())))
    
    # Add all extensions from CSR except Basic Constraints
    for extension in csr.extensions:
        if extension.oid != x509.oid.ExtensionOID.BASIC_CONSTRAINTS:
            builder = builder.add_extension(extension.value, extension.critical)
    
    builder = builder.add_extension(
        x509.AuthorityKeyIdentifier.from_issuer_public_key(cert.public_key()),
        critical=False)

    res = builder.sign(private_key=key, algorithm=hashes.SHA256())
    
    # Save only the certificate
    _save_cert(p, res)
    return res


def _save_cert_and_key(p: Path, cert: x509.Certificate, key: rsa.RSAPrivateKey) -> None:
    _save_cert(p, cert)
    _save_key(p, key)


def _save_cert(p: Path, cert: x509.Certificate) -> None:
    with open(p.with_suffix('.crt'), "wb") as f:
        f.write(cert.public_bytes(encoding=serialization.Encoding.PEM))


def _save_key(p: Path, key: rsa.RSAPrivateKey) -> None:
    with open(p.with_suffix('.key'), "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))


p                  = Path("./ldap")
ca_cert, ca_key    = generate_ca(Path("./ca"), "MLFlow LDAP-Test CA", "MLflow", "LDAP-Test")
cert_csr, cert_key = generate_csr(p, "lldap", "MLflow", "LDAP-Test")
cert               = generate_cert(p, cert_csr, ca_cert, ca_key)
