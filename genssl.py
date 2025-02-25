from cryptography import x509
from cryptography.x509.oid import NameOID
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pathlib import Path
from typing import Tuple
import uuid
import ipaddress


class CertificateAuthority:
    def __init__(self, common_name: str, organization: str, org_unit: str, 
                 key_size: int = 2048, validity: timedelta = timedelta(1, 0, 0)):
        self.common_name = common_name
        self.organization = organization
        self.org_unit = org_unit
        self.key_size = key_size
        self.validity = validity
        self.cert = None
        self.key = None

    def generate(self) -> 'CertificateAuthority':
        key = rsa.generate_private_key(key_size=self.key_size, public_exponent=65537)
        
        name = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, self.common_name),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, self.organization),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, self.org_unit),
        ])
        
        now = datetime.today()
        builder = (x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .not_valid_before(now)
            .not_valid_after(now + self.validity)
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

        self.cert = builder.sign(private_key=key, algorithm=hashes.SHA256())
        self.key = key
        return self

    def store(self, path: Path) -> 'CertificateAuthority':
        if not self.cert or not self.key:
            raise ValueError("Certificate and key not generated yet")
        
        with open(Path(f"{path}.crt"), "wb") as f:
            f.write(self.cert.public_bytes(encoding=serialization.Encoding.PEM))
        
        with open(Path(f"{path}.key"), "wb") as f:
            f.write(self.key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))
        return self


class ServerCertificate:
    def __init__(self, common_name: str, organization: str, org_unit: str, 
                 key_size: int = 2048, validity: timedelta = timedelta(1, 0, 0)):
        self.common_name = common_name
        self.organization = organization
        self.org_unit = org_unit
        self.key_size = key_size
        self.validity = validity
        self.csr = None
        self.cert = None
        self.key = None

    def generate_csr(self) -> 'ServerCertificate':
        key = rsa.generate_private_key(key_size=self.key_size, public_exponent=65537)
        
        csr = (x509.CertificateSigningRequestBuilder()
            .subject_name(x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, self.common_name),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, self.organization),
                x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, self.org_unit),
            ]))
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName(self.common_name),
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
        
        self.csr = csr
        self.key = key
        return self
    
    def sign_with_ca(self, ca: CertificateAuthority) -> 'ServerCertificate':
        now = datetime.today()
        builder = (x509.CertificateBuilder()
            .issuer_name(ca.cert.issuer)
            .subject_name(self.csr.subject)
            .public_key(self.csr.public_key())
            .not_valid_before(now)
            .not_valid_after(now + self.validity)
            .serial_number(int(uuid.uuid4())))
        
        for extension in self.csr.extensions:
            if extension.oid != x509.oid.ExtensionOID.BASIC_CONSTRAINTS:
                builder = builder.add_extension(extension.value, extension.critical)
        
        builder = builder.add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca.cert.public_key()),
            critical=False)

        self.cert = builder.sign(private_key=ca.key, algorithm=hashes.SHA256())
        return self
    
    def store(self, path: Path) -> 'ServerCertificate':
        if not self.cert or not self.key:
            raise ValueError("Certificate and key not generated yet")
        
        with open(Path(f"{path}.crt"), "wb") as f:
            f.write(self.cert.public_bytes(encoding=serialization.Encoding.PEM))
        
        with open(Path(f"{path}.key"), "wb") as f:
            f.write(self.key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))
        return self



if __name__ == "__main__":
    # Generate CA
    ca = CertificateAuthority("MLFlow LDAP-Test CA", "MLflow", "LDAP-Test").generate().store(Path("./ca"))
    
    # Generate Server Certificate
    _ = ServerCertificate("lldap", "MLflow", "LDAP-Test").generate_csr().sign_with_ca(ca).store(Path("./ldap"))
