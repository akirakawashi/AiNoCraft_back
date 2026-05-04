"""MinIO bucket configuration and policies."""

from dataclasses import dataclass


@dataclass
class BucketPolicy:
    """Bucket policy configuration.

    Attributes:
        allow_anonymous_get: Allow anonymous GET (read) access
        allow_anonymous_put: Allow anonymous PUT/DELETE (write) access
    """

    allow_anonymous_get: bool = False
    allow_anonymous_put: bool = False


@dataclass
class BucketConfig:
    """Bucket configuration.

    Attributes:
        name: Bucket name
        policy: Bucket policy configuration
    """

    name: str
    policy: BucketPolicy | None = None

    def get_policy_document(self) -> dict[str, object]:
        """Generate AWS S3 policy document for this bucket."""
        if not self.policy:
            return {}

        statements = [
            {
                "Effect": "Allow" if self.policy.allow_anonymous_get else "Deny",
                "Principal": "*",
                "Action": ["s3:GetObject"],
                "Resource": f"arn:aws:s3:::{self.name}/*",
            },
            {
                "Effect": "Allow" if self.policy.allow_anonymous_put else "Deny",
                "Principal": "*",
                "Action": ["s3:PutObject", "s3:DeleteObject"],
                "Resource": f"arn:aws:s3:::{self.name}/*",
            },
        ]

        return {
            "Version": "2012-10-17",
            "Statement": statements,
        }


# Define all MinIO buckets and their policies
MINIO_BUCKETS = [
    BucketConfig(
        name="avatars",
        policy=BucketPolicy(allow_anonymous_get=True, allow_anonymous_put=False),
    ),
    BucketConfig(
        name="downloads",
        policy=BucketPolicy(allow_anonymous_get=True, allow_anonymous_put=False),
    ),
]
