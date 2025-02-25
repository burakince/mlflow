from cryptography import x509
from cryptography.x509.oid import NameOID
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pathlib import Path
from typing import Tuple
import uuid


def generate_ca(p: Path, co, o, ou: str, size: int = 2048, valid: timedelta = timedelta(1, 0, 0)) -> Tuple[x509.Certificate, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(key_size=size, public_exponent=65537)

    builder = x509.CertificateBuilder()
    builder = builder.subject_name(x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, co),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, o),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, ou),
    ]))
    builder = builder.issuer_name(x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, co),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, o),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, ou),
    ]))
    builder = builder.not_valid_before(datetime.today())
    builder = builder.not_valid_after(datetime.today() + valid)
    builder = builder.serial_number(int(uuid.uuid4()))
    builder = builder.public_key(key.public_key())

    builder = builder.add_extension(
        x509.BasicConstraints(ca=True, path_length=None), critical=True,
    )
    builder = builder.add_extension(
        x509.KeyUsage(
            digital_signature=False,
            content_commitment=False,
            key_encipherment=False,
            data_encipherment=False,
            key_agreement=False,
            key_cert_sign=True,
            crl_sign=True,
            encipher_only=False,
            decipher_only=False
        ), critical=True
    )
    builder = builder.add_extension(
        x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
        critical=False
    )
    builder = builder.add_extension(
        x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()),
        critical=False
    )

    cert = builder.sign(private_key=key, algorithm=hashes.SHA256())

    with open(Path(str(p) + ".crt"), "wb") as f:
        f.write(cert.public_bytes(
            encoding=serialization.Encoding.PEM
    ))
    
    with open(Path(str(p) + ".key"), "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM, 
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))

    return cert, key


def generate_csr(p: Path, co, o, ou: str, size: int = 2048) -> Tuple[x509.CertificateSigningRequest, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(key_size=size, public_exponent=65537)

    csr = x509.CertificateSigningRequestBuilder().subject_name(x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, co),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, o),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, ou),
    ])).add_extension(
        x509.SubjectAlternativeName([
            x509.DNSName(co),
        ]),
        critical=False,
    ).add_extension(
        x509.BasicConstraints(ca=False, path_length=None),
        critical=True,
    ).add_extension(
        x509.KeyUsage(
            digital_signature=True,
            key_encipherment=True,
            content_commitment=False,
            data_encipherment=False,
            key_agreement=False,
            key_cert_sign=False,
            crl_sign=False,
            encipher_only=False,
            decipher_only=False
        ),
        critical=True,
    ).sign(key, hashes.SHA256())

    #with open(Path(str(p) + ".csr"), "wb") as f:
    #    f.write(csr.public_bytes(
    #        encoding=serialization.Encoding.PEM
    #))
    
    with open(Path(str(p) + ".key"), "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM, 
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))

    return csr, key


def generate_cert(p: Path, csr: x509.CertificateSigningRequest, cert: x509.Certificate, key: rsa.RSAPrivateKey, valid: timedelta = timedelta(1, 0, 0)) -> x509.Certificate:
    builder = x509.CertificateBuilder(
        issuer_name      = cert.issuer,
        subject_name     = csr.subject,
        public_key       = csr.public_key(),
        not_valid_before = datetime.today(),
        not_valid_after  = datetime.today() + valid,
        extensions       = csr.extensions,
        serial_number    = int(uuid.uuid4()),
    )

    res = builder.sign(
        private_key = ca_key,
        algorithm   = hashes.SHA256(),
    )

    with open(Path(str(p) + ".crt"), "wb") as f:
        f.write(res.public_bytes(
            encoding=serialization.Encoding.PEM
    ))

    return res



p                  = Path("./ldap")
ca_cert, ca_key    = generate_ca(Path("./ca"), "MLFlow LDAP-Test CA", "MLflow", "LDAP-Test")
cert_csr, cert_key = generate_csr(p, "lldap", "MLflow", "LDAP-Test")
cert               = generate_cert(p, cert_csr, ca_cert, ca_key)
