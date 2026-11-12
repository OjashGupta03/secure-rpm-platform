from app.core.crypto import decrypt_value, encrypt_value


def test_encrypt_decrypt_roundtrip():
    blob = encrypt_value("98.6")
    assert decrypt_value(blob) == "98.6"


def test_ciphertext_differs_each_call():
    a = encrypt_value("120")
    b = encrypt_value("120")
    assert a != b  # random nonce per call
    assert decrypt_value(a) == decrypt_value(b) == "120"
