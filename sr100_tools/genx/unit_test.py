import unittest
import os
from src.params_parser import *

class TestCryptoMethods(unittest.TestCase):
    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)
        self.params = StoreParamsT()

    def test_crypto_get_rsa_modulus(self):
        self.params.payload_input_file = 'test_files/pubkey_test.txt'
        with open(self.params.payload_input_file, 'w') as pubkey_test:
            pubkey_test.write('''-----BEGIN RSA PUBLIC KEY-----
MEgCQQCo9+BpMRYQ/dL3DS2CyJxRF+j6ctbT3/Qp84+KeFhnii7NT7fELilKUSnx
S30WAvQCCo2yU1orfgqr41mM70MBAgMBAAE=
-----END RSA PUBLIC KEY-----''')
        self.assertTrue(crypto_get_rsa_modulus(self.params))
        os.remove(self.params.payload_input_file)

        # This are the length and the bytes presentation of the modulus in the pubkey
        self.assertEqual(self.params.body_len, 64)
        self.assertEqual(self.params.p_body, b'\xa8\xf7\xe0i1\x16\x10\xfd\xd2\xf7\r-\x82\xc8\x9cQ\x17\xe8\xfar\xd6\xd3\xdf\xf4)\xf3\x8f\x8axXg\x8a.\xcdO\xb7\xc4.)JQ)\xf1K}\x16\x02\xf4\x02\n\x8d\xb2SZ+~\n\xab\xe3Y\x8c\xefC\x01')

    def test_crypto_get_random(self):
        length = 64
        rand = crypto_get_random(length)
        self.assertEqual(length, len(rand))

    def test_crypto_aes256_dec(self):
        ciphertext = b'\xa0\xb2F\x88z\xb6\xc9@\xf1\xd1\xde\xd0\xefG\xcf\xb7'
        key = b'AAAAAAAAAAAAAAAA'
        iv = b'AAAAAAAAAAAAAAAA'
        self.assertEqual(crypto_aes256_dec(ciphertext, key, iv), b'Hello world!')

    def test_crypto_aes256_enc(self):
        plaintext = b'Hello world!'
        key = b'AAAAAAAAAAAAAAAA'
        iv = b'AAAAAAAAAAAAAAAA'
        self.assertEqual(crypto_aes256_enc(plaintext, key, iv), b'\xa0\xb2F\x88z\xb6\xc9@\xf1\xd1\xde\xd0\xefG\xcf\xb7')

    def test_crypto_sha256(self):
        plaintext = b'Hello world!'
        self.assertEqual(crypto_sha256(plaintext), b'\xc0S^K\xe2\xb7\x9f\xfd\x93)\x13\x05Ck\xf8\x891NJ?\xae\xc0^\xcf\xfc\xbb}\xf3\x1a\xd9\xe5\x1a')

    def test_crypto_sha384(self):
        plaintext = b'Hello world!'
        self.assertEqual(crypto_sha384(plaintext), b'\x86%_\xa2\xc3nK0\x96\x9e\xae\x17\xdc4\xc7r\xcb\xeb\xdf\xc5\x8bX@9\x00\xbe\x87aN\xb1\xa3K\x87\x80&?%^\xb5\xe6\\\xa9\xbb\xb8d\x1c\xcc\xfe')

    def test_crypto_rsa_sign(self):
        privkey_name = 'test_files/privkey_test.txt'
        with open(privkey_name, 'w') as private_key:
            private_key.write('''-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAijgGotcSGfHTY6rR0lQAn5cHEaQQAZ6A/vdWyDV3NdwMp62Z
R68S+Fvn3Ed19jcI82aVTpZxd3NBwpQdNuj2bZvxk3GI0/uxUS/oLxzdCGs7l3Gw
H7jsNEeIQ84Gcq76RI6CL3r8xRKLiQAx51Lg+ZSypr6RhE8Tltu0vuXAJd1CC48d
PmV6YoUeRXH6oiSTq6XWB1LgKeB0V+xEoRop4GrfaQUXOvsqpysTLS1U3Lstnx1n
dt6zhduoLsIjlRVCaK5G6+LeiM2PfPWQNTcjzFAM6YlHT7ffof8+jzh3za9UqVRy
V663QYmFZ0EzfjVg0vGNwLQbiRNsjCaRyehISwIDAQABAoIBAEYpspSvAG1TKK+L
Yv+VzMs2a0w1MDriLzE+dTskiOM6VOI5aXnOEZ8paEWVsPfPcCe+h0Rhci/kvhj7
/uiE0bNKWhMyqvaQ6a4A16gyyrEfXhy+hV1VDfJr7WweBX/p+vkaLlPT5sRTaame
A7cdhz6qkRW73zp+ub72wIW3MxcEvQ1KiuVyX/0vKvtak5qAIe4VrLU0N6hfCgwV
/7Rx1gyk7gtFfBD1P/QvRUGoFzBWmQJ/pJLpHvLBVYKU6rMnK/p5Hf75ljqTxvEv
/EyrISpeGS3T00Xkfd6oSPSgTio3Il2aI7GqUWeoDdiAfHLIt+FIzSyMj0WXXnTY
wP/oFCECgYEA2kzZ4j0KuhfILJ1RwngJcNzRs42gTj0KArcU+TVuv36WFjSEHFmP
lTuNrlEjZpIDDXAZEBNEJfDSA3ixn3W/2teG/MwRNfqFUr2xnbUvtF7hCI8rIWDq
EDb2OGpLWzq4APYVukt61L4DEZ0KdMihgG08h0nF5oUlorfV3UczqgcCgYEAoha+
J8SF1SI09IfbKAb82EWNKh4WkZUAKdMS+rIdKRP2/jUPvohFMY7VX0/a1JZFbYa0
gRuIr6guTPzm8+qACsBscwfYJNCRTFCGquZop/19w6c/0jJ1/uswHjUbYj3JdbTv
HGx/tDR4V+YNVo3kj+QtomsJM+vmXrZPfZAGbp0CgYEAsi6qZay3db/1ptzeIGKE
KjhDflBqeZH++spfdy5y8CEt9n/1GYLM3N1YPuGBiLZDgZNvEZz4MhPICAdazDJ7
X/AuAWe74JhUfH3TXUvH3WzYN3lMlhkZ1BRYkyHH0nYyPK6ge4gigUV7EcRiBYLB
uCbxkefYfdlOJ+vvx4bXl78CgYEAlHnizEjgE2GXQpwkK+FiwbXMXtVa9RaZJLbd
/tkjjxpjuW7fsjffskrVt85NdUkF5hNry4xuRAH6D7nm0W5wxeiIL0LzQp3vSwnE
ok4XdjLlflD5TFG+9rl3xWP+ZpqUrYcFNXNJ88fQqSvp8exef1SUXOBReMdRqla0
MB+7VJ0CgYBl1t9RUTimnM0CnomFE4v9gaadCND2JxStsR2mDwWc+/WWDYjQ9xmA
0cV5yYfO0xxRfLxU8fmM0uEDhO/jOjjs6uIlK2tUaSeFuPWN0uwPiXn33I6ruhSQ
HoFhCTbgBbTAeUqB/48AEPNfXe5U1n6+ISyMTGm3JqphhJfBJqLpiA==
-----END RSA PRIVATE KEY-----''')
        self.assertEqual(crypto_rsa_sign(b'Hello world!', privkey_name), b'l\xed\xe0D\xaf\xa1\xe6W\x00\xf2=\x92\xfc\x11fl\x17B\xa7\xf3H\x8f\xcf\x9f\x07\x15M~\x88\x87\xabm+\x8d\xeb\xba\x01h\x93\xca\xd8\xfb\xfd\xd8\xc1\xa5\xebsI\x10\xed*\xe3\x0cA\x82\x1b\\\x8a\xe9c]\x95\xd6\x9a\xe7\xb8\x9e\x8eD\xc1\xd6J\x7f\x01\xaf\x19{\x06\xae\xe7\xb4\x97\xe7I[\xdbgEJ\x0ex\x11\x05\xf6\xb9W\xac\x1c\xe0cB\xb1\xf4s\\(\x96\t\xa8*Y\xfd=*,D\r\n\xa0\xf9A\xd5\xdf\xe8\xfb\xcbm\x90z\xaf\xaa\x1a\x9b\xb9R\x13\xe7v\x0b\xe4\x1b\x1d\x85\xb2\xbf\x0c\x03q;\xe4\xb9\x8amjM3H\xb2\xbf\xaaT8\xbd\x85\xaezG\x0c\x91\x08\xad9\xb7\xbbD\xe4\x84\'\xbfP\xe8\xf7\x0e\x0e\x85\x13\x9d\x17\x00\x836%L`y\x19Sh\xd6\x8c\x00\x97\x83z\x8b\xb2=H?N\x1a\x17\xbe\xafLZ\x0bV\x9b\xc16e\xab\x85w\xdf\xb04\xfd\xcf\xac\xdb{\xc7v\x11Wl\x9f\xc8\xfb"w\xc9N\xd4\xad(\x87,\xc5/4\x92g')
        os.remove(privkey_name)


if __name__ == '__main__':
    unittest.main()
