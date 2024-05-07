module "s3" {
  source  = "terraform-aws-modules/s3-bucket/aws"
  version = "3.13.0"

  bucket         = var.bucket_name
  attach_policy  = var.attach_policy
  policy         = var.policy
  lifecycle_rule = var.lifecycle_rule_inputs
  force_destroy  = var.force_destroy

  block_public_acls       = var.block_public_acls
  block_public_policy     = var.block_public_policy
  ignore_public_acls      = var.ignore_public_acls
  restrict_public_buckets = var.restrict_public_buckets

  server_side_encryption_configuration = {
    rule = {
      apply_server_side_encryption_by_default = {
        sse_algorithm = "AES256"
      }
    }
  }

  website = var.website_map

  # TODO Set up access logging bucket for CSOC
  #logging = {
  #  target_bucket = var.target_bucket
  #  target_prefix = var.target_prefix
  #}
  versioning = {
    enabled = true
  }
}
