from passlib.context import CryptContext

# bcrypt is the only supported scheme. "deprecated='auto'" will upgrade
# hashes using weaker schemes transparently on next login.
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
