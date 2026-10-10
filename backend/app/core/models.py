"""Import every module's models so Alembic and create_all see all tables."""
from app.challenges.models import Challenge  # noqa: F401
from app.progress.models import Progress  # noqa: F401
from app.submissions.models import Submission  # noqa: F401
from app.users.models import User  # noqa: F401
