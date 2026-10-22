"""One-hour self-signed loopback fixture only. Called over a private process pipe.
Never run this directly into a public log. No existing credentials are read.
"""
from datetime import datetime, timezone, timedelta
import ipaddress
import json
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
key=ec.generate_private_key(ec.SECP256R1())
name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "BuyerOS synthetic loopback")])
now=datetime.now(timezone.utc)
cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
      .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1))
      .not_valid_after(now+timedelta(hours=1))
      .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),False)
      .sign(key,hashes.SHA256()))
print(json.dumps({"key":key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,
                                       serialization.NoEncryption()).decode("ascii"),
                  "cert":cert.public_bytes(serialization.Encoding.PEM).decode("ascii")}))
