import hashlib
from typing import ClassVar

from pwdlib import PasswordHash


class EncryptionService:
    password_hash: ClassVar[PasswordHash] = PasswordHash.recommended()

    @classmethod
    def hash_password(cls, password: str) -> str:
        """
        Hash a given password using bcrypt.

        Args:
            password (str): The password to hash.

        Returns:
            str: The hashed password.
        """
        return cls.password_hash.hash(password)

    @classmethod
    def verify_password(cls, plain_password: str, hashed_password: str) -> bool:
        """
        Verify that a given password matches a hashed password using bcrypt.

        Args:
            plain_password (str): The password to verify.
            hashed_password (str): The hashed password to compare against.

        Returns:
            bool: True if the password matches the hashed password, False otherwise.
        """
        return cls.password_hash.verify(plain_password, hashed_password)

    @staticmethod
    def sha256(data: str) -> str:
        """
        Compute the SHA-256 hash of a given string.

        Args:
            data (str): The string to hash.

        Returns:
            str: The SHA-256 hash of the string.
        """
        return hashlib.sha256(data.encode()).hexdigest()
