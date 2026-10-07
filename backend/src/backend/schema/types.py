import uuid
from datetime import datetime

import strawberry


@strawberry.type
class Repository:
    id: uuid.UUID
    url: str
    owner: str
    name: str
    default_branch: str | None


@strawberry.type
class AnalysisJob:
    id: uuid.UUID
    repository_id: uuid.UUID
    status: str
    error_message: str | None
    created_at: datetime
