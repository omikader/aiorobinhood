import asyncio
import contextlib
import socket
import ssl
import tempfile
from datetime import datetime, timedelta

import aiohttp
import aiohttp.test_utils


class FakeResolver:
    def __init__(self):
        self._servers = {}

    def add(self, host, port, target_port):
        """Add an entry to the resolver."""
        self._servers[host, port] = target_port

    async def resolve(self, host, port=0, family=socket.AF_INET):
        """Resolve a host/port pair into a connectable address."""
        try:
            fake_port = self._servers[host, port]
            return [
                {
                    "hostname": host,
                    "host": "127.0.0.1",
                    "port": fake_port,
                    "family": family,
                    "proto": 0,
                    "flags": socket.AI_NUMERICHOST,
                }
            ]
        except KeyError:
            raise OSError(f"No test server known for {host}")


class CaseControlledTestServer(aiohttp.test_utils.RawTestServer):
    """Test server that relies on test case to supply responses and control timing."""

    def __init__(self, ssl=None, **kwargs):
        super().__init__(self._handle_request, **kwargs)
        self._ssl = ssl
        self._requests = asyncio.Queue()
        self._responses = {}

    async def start_server(self, **kwargs):
        kwargs.setdefault("ssl", self._ssl)
        await super().start_server(**kwargs)

    async def close(self):
        """Cancel all pending requests."""
        for future in self._responses.values():
            future.cancel()
        await super().close()

    async def _handle_request(self, request):
        """Push the request to the test case and wait until it provides a response."""
        self._responses[id(request)] = response = asyncio.Future()
        self._requests.put_nowait(request)

        try:
            # Wait until the test case provides a response
            return await response
        finally:
            del self._responses[id(request)]

    async def receive_request(self, timeout=None):
        """Wait until the test server receives a request."""
        return await asyncio.wait_for(self._requests.get(), timeout=timeout)

    def send_response(self, request, *args, **kwargs):
        """Send a web resposne from the test case to the client."""
        response = aiohttp.web.Response(*args, **kwargs)
        self._responses[id(request)].set_result(response)


class TemporaryCertificate:
    def __enter__(self):
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        subject = issuer = x509.Name(
            [x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, "localhost")]
        )

        with contextlib.ExitStack() as stack:
            key = rsa.generate_private_key(
                public_exponent=65537, key_size=1024, backend=default_backend()
            )

            key_file = stack.enter_context(tempfile.NamedTemporaryFile())
            key_file.write(
                key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )
            key_file.flush()

            cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.utcnow())
                .not_valid_after(datetime.utcnow() + timedelta(days=1))
                .add_extension(
                    x509.SubjectAlternativeName(
                        [x509.DNSName("localhost"), x509.DNSName("127.0.0.1")]
                    ),
                    critical=False,
                )
                .sign(key, hashes.SHA256(), default_backend())
            )

            cert_file = stack.enter_context(tempfile.NamedTemporaryFile())
            cert_file.write(cert.public_bytes(serialization.Encoding.PEM))
            cert_file.flush()

            self._key_file, self._cert_file = key_file, cert_file
            stack.pop_all()

        return self

    def __exit__(self, exc, exc_type, tb):
        self._key_file.close()
        self._cert_file.close()

    def load_verify(self, context):
        """Load the certificate for verification purposes."""
        context.load_verify_locations(cafile=self._cert_file.name)

    def client_context(self):
        """A client-side SSL context accepting the certificate, and no others."""
        context = ssl.SSLContext()
        context.verify_mode = ssl.VerifyMode.CERT_REQUIRED
        self.load_verify(context)
        return context

    def server_context(self):
        """A server-side SSL context using the certificate."""
        context = ssl.SSLContext()
        context.load_cert_chain(self._cert_file.name, keyfile=self._key_file.name)
        return context
