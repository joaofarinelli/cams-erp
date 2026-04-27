# Bootstrap

Run **once per account**. Creates the S3 + DynamoDB used as Terraform backend
for everything else. Local state file is committed-ignored.

If you re-run it, you'll error harmlessly on resources-already-exist.
