from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
import os

# ---------------------------------------------------------------------------
# SECRET_KEY — must be set in the environment, never hardcoded.
#
# Generate a secure key with:
#   python -c "import secrets; print(secrets.token_hex(32))"
# Then add it to your .env file:
#   SECRET_KEY=<the generated value>
# ---------------------------------------------------------------------------
_secret = os.environ.get("SECRET_KEY", "").strip()
if not _secret:
    raise RuntimeError(
        "SECRET_KEY environment variable is not set. "
        "Generate a secure key with:\n"
        '  python -c "import secrets; print(secrets.token_hex(32))"\n'
        "and add SECRET_KEY=<value> to your .env file."
    )

SECRET_KEY                = _secret
ALGORITHM                 = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        password = password[:72]
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    if len(plain.encode("utf-8")) > 72:
        plain = plain[:72]
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
