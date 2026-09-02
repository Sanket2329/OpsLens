from slugify import slugify

from app.core.logging import get_logger
from app.models.organization import Organization
from app.models.user import User
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserRegister
from app.security.hashing import hash_password, verify_password
from app.security.jwt import create_access_token

logger = get_logger(__name__)


class AuthService:
    def __init__(self, db):
        self.db = db
        self.users = UserRepository(db)
        self.organizations = OrganizationRepository(db)

    def register(self, data: UserRegister) -> str:
        existing = self.users.get_by_email(data.email)

        if existing:
            logger.warning("Registration attempt with existing email: %s", data.email)
            raise ValueError("Email already registered")

        slug = slugify(data.organization_name)
        organization = self.organizations.get_by_slug(slug)

        is_new_org = organization is None

        if is_new_org:
            organization = self.organizations.create(
                Organization(
                    name=data.organization_name,
                    slug=slug,
                )
            )
            logger.info("Created organization '%s' (slug=%s)", data.organization_name, slug)

        # First user of a new organisation becomes admin; subsequent users are members.
        role = "admin" if is_new_org else "member"

        user = self.users.create(
            User(
                name=data.name,
                email=data.email,
                password_hash=hash_password(data.password),
                role=role,
                organization_id=organization.id,
            )
        )

        logger.info(
            "User registered: id=%d email=%s role=%s org_id=%d",
            user.id,
            user.email,
            role,
            organization.id,
        )

        return create_access_token(
            {
                "sub": str(user.id),
                "email": user.email,
                "organization_id": organization.id,
            }
        )

    def login(self, email: str, password: str) -> str:
        user = self.users.get_by_email(email)

        if not user or not verify_password(password, user.password_hash):
            logger.warning("Failed login attempt for email: %s", email)
            raise ValueError("Invalid credentials")

        logger.info("User logged in: id=%d email=%s", user.id, user.email)

        return create_access_token(
            {
                "sub": str(user.id),
                "email": user.email,
                "organization_id": user.organization_id,
            }
        )
